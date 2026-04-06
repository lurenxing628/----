from __future__ import annotations

from typing import Any, Dict

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models.enums import BatchPriority, BatchStatus, ReadyStatus

_MISSING = object()


def _resolve_part(svc, part_no: Any):
    part_no_text = svc._normalize_text(part_no)
    if not part_no_text:
        raise ValidationError("“图号”不能为空", field="图号")
    part = svc.part_repo.get(part_no_text)
    if not part:
        raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{part_no_text}”不存在，请先在工艺管理中维护零件。")
    return part_no_text, part


def _resolved_part_name(svc, *, part, part_name: Any) -> Any:
    normalized = svc._normalize_text(part_name)
    return normalized or getattr(part, "part_name", None)


def _validated_quantity(svc, quantity: Any) -> int:
    normalized = svc._normalize_int(quantity, field="数量", allow_none=False)
    if normalized is None or normalized <= 0:
        raise ValidationError("“数量”必须大于 0", field="数量")
    return int(normalized)



def _validated_priority(svc, priority: Any) -> str:
    normalized = svc._normalize_text(priority) or BatchPriority.NORMAL.value
    svc._validate_enum(normalized, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
    return normalized


def _validated_ready_status(svc, ready_status: Any) -> str:
    normalized = svc._normalize_text(ready_status) or ReadyStatus.YES.value
    svc._validate_enum(normalized, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")
    return normalized


def _validated_status(svc, status: Any) -> str:
    normalized = svc._normalize_text(status) or BatchStatus.PENDING.value
    svc._validate_enum(
        normalized,
        (
            BatchStatus.PENDING.value,
            BatchStatus.SCHEDULED.value,
            BatchStatus.PROCESSING.value,
            BatchStatus.COMPLETED.value,
            BatchStatus.CANCELLED.value,
        ),
        "状态",
    )
    return normalized


def _ensure_part_switch_allowed(*, current_part_no: Any, next_part_no: str, auto_generate_ops: Any) -> None:
    if auto_generate_ops is _MISSING:
        return
    current = str(current_part_no or "").strip()
    if current and current != next_part_no and not bool(auto_generate_ops):
        raise ValidationError("已存在批次图号变更，必须开启自动生成工序后再试。", field="图号")


def _part_updates(
    svc,
    *,
    current_part_no: Any,
    auto_generate_ops: Any,
    part_no: Any,
    part_name: Any,
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if part_no is not _MISSING:
        next_part_no, part = _resolve_part(svc, part_no)
        _ensure_part_switch_allowed(current_part_no=current_part_no, next_part_no=next_part_no, auto_generate_ops=auto_generate_ops)
        updates["part_no"] = next_part_no
        if part_name is _MISSING:
            updates["part_name"] = getattr(part, "part_name", None)
    if part_name is not _MISSING:
        updates["part_name"] = svc._normalize_text(part_name)
    return updates


def build_create_payload(
    svc,
    *,
    batch_id: Any,
    part_no: Any,
    quantity: Any,
    due_date: Any = None,
    priority: Any = BatchPriority.NORMAL.value,
    ready_status: Any = ReadyStatus.YES.value,
    ready_date: Any = None,
    status: Any = BatchStatus.PENDING.value,
    remark: Any = None,
    part_name: Any = None,
) -> Dict[str, Any]:
    batch_id_text = svc._normalize_text(batch_id)
    if not batch_id_text:
        raise ValidationError("“批次号”不能为空", field="批次号")
    part_no_text, part = _resolve_part(svc, part_no)
    return {
        "batch_id": batch_id_text,
        "part_no": part_no_text,
        "part_name": _resolved_part_name(svc, part=part, part_name=part_name),
        "quantity": _validated_quantity(svc, quantity),
        "due_date": svc._normalize_date(due_date),
        "priority": _validated_priority(svc, priority),
        "ready_status": _validated_ready_status(svc, ready_status),
        "ready_date": svc._normalize_date(ready_date),
        "status": _validated_status(svc, status),
        "remark": svc._normalize_text(remark),
    }


def build_update_payload(
    svc,
    *,
    current_part_no: Any,
    auto_generate_ops: Any = _MISSING,
    part_no: Any = _MISSING,
    quantity: Any = _MISSING,
    due_date: Any = _MISSING,
    priority: Any = _MISSING,
    ready_status: Any = _MISSING,
    ready_date: Any = _MISSING,
    status: Any = _MISSING,
    remark: Any = _MISSING,
    part_name: Any = _MISSING,
) -> Dict[str, Any]:
    updates = _part_updates(
        svc,
        current_part_no=current_part_no,
        auto_generate_ops=auto_generate_ops,
        part_no=part_no,
        part_name=part_name,
    )
    if quantity is not _MISSING:
        updates["quantity"] = _validated_quantity(svc, quantity)
    if due_date is not _MISSING:
        updates["due_date"] = svc._normalize_date(due_date)
    if priority is not _MISSING:
        updates["priority"] = _validated_priority(svc, priority)
    if ready_status is not _MISSING:
        updates["ready_status"] = _validated_ready_status(svc, ready_status)
    if ready_date is not _MISSING:
        updates["ready_date"] = svc._normalize_date(ready_date)
    if status is not _MISSING:
        updates["status"] = _validated_status(svc, status)
    if remark is not _MISSING:
        updates["remark"] = svc._normalize_text(remark)
    return updates
