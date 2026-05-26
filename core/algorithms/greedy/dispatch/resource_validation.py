from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.models.scheduler_public_errors import public_safe_identifier, public_safe_label

from ..auto_assign import (
    AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS,
    AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL,
    AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID,
)

RESOURCE_REASON_FIXED = "fixed"
RESOURCE_REASON_MANUAL_MISSING = "manual_missing"
RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE = "auto_assign_unavailable"


def internal_resource_validation_message(
    *,
    batch: Any,
    op: Any,
    meta: Dict[str, Any],
    machine_id: str,
    operator_id: str,
    reason: str,
    auto_assign_reason: str,
) -> Tuple[str, Dict[str, Any]]:
    details = _operation_public_details(batch=batch, op=op, meta=meta)
    operation_display = _operation_display(op_code=str(details.get("op_code") or ""), seq=int(details.get("seq") or 0))
    operation_context = _operation_context_from_details(details)
    if reason == RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE:
        message, public_reason = _auto_assign_resource_message(
            details=details,
            operation_display=operation_display,
            operation_context=operation_context,
            auto_assign_reason=auto_assign_reason,
        )
        details.update({"user_message": message, "reason": public_reason, "auto_assign_reason": auto_assign_reason})
        return message, details

    missing_fields = _missing_internal_resource_fields(op=op, machine_id=machine_id, operator_id=operator_id)
    message = (
        f"批次 {details['batch_id']} 的{operation_display}"
        f"（{operation_context}）"
        f"缺少{'、'.join(missing_fields)}，"
        "请到批次详情补齐后再排产。"
    )
    details.update({"user_message": message, "reason": "missing_internal_resource", "missing_fields": list(missing_fields)})
    return message, details


def _operation_public_details(*, batch: Any, op: Any, meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "op_id": meta.get("op_id"),
        "batch_id": public_safe_identifier(getattr(op, "batch_id", None) or meta.get("batch_id")) or "-",
        "op_code": public_safe_identifier(getattr(op, "op_code", None)),
        "seq": int(meta.get("seq") or 0),
        "op_type_name": public_safe_label(getattr(op, "op_type_name", None)),
        "part_no": public_safe_identifier(getattr(batch, "part_no", None) or getattr(op, "part_no", None)),
        "part_name": public_safe_label(getattr(batch, "part_name", None) or getattr(op, "part_name", None)),
        "piece_id": public_safe_identifier(getattr(op, "piece_id", None)),
    }


def _operation_context_from_details(details: Dict[str, Any]) -> str:
    return _operation_context(
        op_code=str(details.get("op_code") or ""),
        seq=int(details.get("seq") or 0),
        op_type_name=str(details.get("op_type_name") or ""),
        part_no=str(details.get("part_no") or ""),
        part_name=str(details.get("part_name") or ""),
        piece_id=str(details.get("piece_id") or ""),
    )


def _auto_assign_resource_message(
    *,
    details: Dict[str, Any],
    operation_display: str,
    operation_context: str,
    auto_assign_reason: str,
) -> Tuple[str, str]:
    prefix = f"批次 {details['batch_id']} 的{operation_display}（{operation_context}）"
    if auto_assign_reason == AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID:
        return (
            f"{prefix}缺少自动派工所需工种信息，请补齐工种或固定设备后再排产。",
            "auto_assign_inputs_missing",
        )
    if auto_assign_reason == AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL:
        return (
            f"{prefix}自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
            "auto_assign_resource_pool_incomplete",
        )
    if auto_assign_reason == AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS:
        return (f"{prefix}工时不合法，请修正工时后再排产。", "invalid_internal_work_hours")
    return (
        f"{prefix}没有找到可用的自动分配设备和人员组合，请检查设备工种、人员可操作设备和资源可用时间后再排产。",
        "auto_assign_no_resource_combination",
    )


def _operation_display(*, op_code: str, seq: int) -> str:
    if op_code:
        return f"工序 {op_code}"
    if seq:
        return f"工序顺序 {seq}"
    return "工序"


def _operation_context(
    *,
    op_code: str,
    seq: int,
    op_type_name: str,
    part_no: str,
    part_name: str,
    piece_id: str,
) -> str:
    parts: List[str] = []
    if op_code and seq:
        parts.append(f"顺序 {seq}")
    parts.append(f"工种 {op_type_name or '未填写'}")
    part_context = _part_context(part_no=part_no, part_name=part_name, piece_id=piece_id)
    if part_context:
        parts.append(part_context)
    return "，".join(parts)


def _part_context(*, part_no: str, part_name: str, piece_id: str) -> str:
    parts: List[str] = []
    if part_no:
        parts.append(f"图号 {part_no}")
    if part_name:
        parts.append(f"零件 {part_name}")
    if piece_id:
        parts.append(f"件号 {piece_id}")
    return "，".join(parts)


def _missing_internal_resource_fields(*, op: Any, machine_id: str, operator_id: str) -> List[str]:
    original_machine_id = str(getattr(op, "machine_id", None) or "").strip()
    original_operator_id = str(getattr(op, "operator_id", None) or "").strip()
    missing_fields: List[str] = []
    if not original_machine_id:
        missing_fields.append("设备")
    if not original_operator_id:
        missing_fields.append("人员")
    if missing_fields:
        return missing_fields
    if not machine_id:
        missing_fields.append("设备")
    if not operator_id:
        missing_fields.append("人员")
    return missing_fields or ["设备", "人员"]
