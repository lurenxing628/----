from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.errors import ValidationError
from core.models.scheduler_public_errors import public_safe_identifier, public_safe_label
from core.services.scheduler.run.auto_assign_resource_errors import first_public_auto_assign_resource_error


def _positive_int(value: Any) -> Optional[int]:
    # 持久化错误归一哨兵：坏 id 保持 None，避免盖掉原始 no_actionable 诊断。
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _normalize_positive_ids(raw_ids: Optional[Set[int]]) -> Set[int]:
    out: Set[int] = set()
    for raw_id in raw_ids or ():
        op_id = _positive_int(raw_id)
        if op_id is not None:
            out.add(op_id)
    return out


def _operation_row(op: Any) -> Dict[str, Any]:
    return op if isinstance(op, dict) else vars(op)


def _safe_missing_fields(row: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if not str(row.get("machine_id") or "").strip():
        missing.append("设备")
    if not str(row.get("operator_id") or "").strip():
        missing.append("人员")
    return missing


def _missing_internal_resource_sample(row: Dict[str, Any], *, op_id: int) -> Dict[str, Any]:
    seq = _positive_int(row.get("seq", 0)) or 0
    return {
        "op_id": int(op_id),
        "batch_id": public_safe_identifier(row.get("batch_id", "")),
        "op_code": public_safe_identifier(row.get("op_code", "")),
        "seq": int(seq),
        "op_type_name": public_safe_label(row.get("op_type_name", "")),
        "missing_fields": _safe_missing_fields(row),
    }


def missing_internal_resource_samples(
    operations: Optional[List[Any]],
    missing_internal_resource_op_ids: Optional[Set[int]],
) -> List[Dict[str, Any]]:
    missing_ids = _normalize_positive_ids(missing_internal_resource_op_ids)
    if not missing_ids:
        return []

    matching_operations: List[Tuple[Tuple[str, int, int], Dict[str, Any], int]] = []
    for op in operations or ():
        if op is None:
            continue
        row = _operation_row(op)
        op_id = _positive_int(row.get("id", 0))
        if op_id is not None and op_id in missing_ids:
            sort_key = (str(row.get("batch_id") or ""), int(row.get("seq") or 0), op_id)
            matching_operations.append((sort_key, row, op_id))
    return [
        _missing_internal_resource_sample(row, op_id=op_id)
        for _, row, op_id in sorted(matching_operations, key=lambda item: item[0])
    ]


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
    operations: Optional[List[Any]] = None,
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
