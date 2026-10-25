from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.models.scheduler_public_errors import public_safe_identifier, public_safe_label
from core.services.scheduler.run.auto_assign_resource_errors import first_public_auto_assign_resource_error


def _missing_resource_fields(op: BatchOperation) -> List[str]:
    # 与缺资源集合同一口径（workbench/run/input._missing_internal_resources）：资源为 None 即缺。
    missing: List[str] = []
    if op.machine_id is None:
        missing.append("设备")
    if op.operator_id is None:
        missing.append("人员")
    return missing


def _missing_internal_resource_sample(op: BatchOperation) -> Dict[str, Any]:
    return {
        "op_id": op.id,
        "batch_id": public_safe_identifier(op.batch_id),
        "op_code": public_safe_identifier(op.op_code),
        "seq": op.seq,
        "op_type_name": public_safe_label(op.op_type_name),
        "missing_fields": _missing_resource_fields(op),
    }


def missing_internal_resource_samples(
    operations: List[BatchOperation],
    missing_internal_resource_op_ids: Optional[Set[int]],
) -> List[Dict[str, Any]]:
    # 工序来自排产输入构造时已严格校验的 BatchOperation（workbench/facts/run_input_rows.operation_model），
    # 缺资源 id 集合也由这些工序 id 派生，这里直接使用。
    if not missing_internal_resource_op_ids:
        return []
    matching = [op for op in operations if op.id in missing_internal_resource_op_ids]
    matching.sort(key=lambda op: (op.batch_id, op.seq, op.id))
    return [_missing_internal_resource_sample(op) for op in matching]


def _format_missing_internal_resource_sample(samples: List[Dict[str, Any]]) -> str:
    messages: List[str] = []
    for item in samples[:10]:
        label_parts = [
            item["batch_id"],
            f"工序{item['seq']}",
            item["op_type_name"],
        ]
        label = " / ".join([part for part in label_parts if part])
        missing_text = "、".join(item["missing_fields"]) or "设备/人员"
        messages.append(f"{label} 缺{missing_text}")
    return "；".join(messages)


def raise_no_actionable_schedule_error(
    validation_errors: Optional[List[str]] = None,
    *,
    operations: List[BatchOperation],
    missing_internal_resource_op_ids: Optional[Set[int]] = None,
) -> None:
    details: Dict[str, Any] = {"reason": "no_actionable_schedule_rows"}
    if validation_errors:
        details["validation_errors"] = list(validation_errors)

    public_root_error_message = first_public_auto_assign_resource_error(validation_errors)
    missing_samples = missing_internal_resource_samples(operations, missing_internal_resource_op_ids)
    if missing_samples:
        total = len(missing_samples)
        details["missing_internal_resource_count"] = total
        details["missing_internal_resource_ops"] = missing_samples[:10]
        if not public_root_error_message:
            sample_text = _format_missing_internal_resource_sample(missing_samples)
            suffix = f"；还有 {total - 10} 条未展示" if total > 10 else ""
            details["user_message"] = (
                f"本次排产没有生成可保存结果，存在自制工序缺设备/人员："
                f"{sample_text}{suffix}。请先到批次工序补充页补齐后重试。"
            )
    if public_root_error_message:
        details["user_message"] = (
            "本次排产没有生成可保存结果，"
            f"{public_root_error_message.rstrip('。')}"
            "。"
        )
    raise ValidationError(
        "本次排产没有生成可保存的结果，系统没有写入新排产。请检查批次是否有可排工序、设备和人员是否已补齐。",
        field="排产结果",
        details=details,
    )


__all__ = ["missing_internal_resource_samples", "raise_no_actionable_schedule_error"]
