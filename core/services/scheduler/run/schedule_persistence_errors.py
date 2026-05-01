from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError


def _positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _normalize_positive_ids(raw_ids: Optional[Set[int]]) -> Set[int]:
    out: Set[int] = set()
    for raw_id in set(raw_ids or set()):
        op_id = _positive_int(raw_id)
        if op_id is not None:
            out.add(op_id)
    return out


def _operation_sort_key(op: Any) -> Tuple[str, int, int]:
    return (
        str(getattr(op, "batch_id", "") or ""),
        int(getattr(op, "seq", 0) or 0),
        int(getattr(op, "id", 0) or 0),
    )


def _missing_fields(op: Any) -> List[str]:
    missing: List[str] = []
    if not str(getattr(op, "machine_id", "") or "").strip():
        missing.append("设备")
    if not str(getattr(op, "operator_id", "") or "").strip():
        missing.append("人员")
    return missing


def _missing_internal_resource_sample(op: Any, *, op_id: int) -> Dict[str, Any]:
    return {
        "op_id": op_id,
        "batch_id": str(getattr(op, "batch_id", "") or ""),
        "op_code": str(getattr(op, "op_code", "") or ""),
        "seq": int(getattr(op, "seq", 0) or 0),
        "op_type_name": str(getattr(op, "op_type_name", "") or ""),
        "missing_fields": _missing_fields(op),
    }


def _missing_internal_resource_samples(
    operations: Optional[List[Any]],
    missing_internal_resource_op_ids: Optional[Set[int]],
) -> List[Dict[str, Any]]:
    missing_ids = _normalize_positive_ids(missing_internal_resource_op_ids)
    if not missing_ids:
        return []

    samples: List[Dict[str, Any]] = []
    for op in sorted(list(operations or []), key=_operation_sort_key):
        op_id = _positive_int(getattr(op, "id", 0))
        if op_id is not None and op_id in missing_ids:
            samples.append(_missing_internal_resource_sample(op, op_id=op_id))
    return samples


def _format_missing_internal_resource_sample(samples: List[Dict[str, Any]]) -> str:
    messages: List[str] = []
    for item in samples[:10]:
        label_parts = [
            str(item.get("batch_id") or "").strip(),
            f"工序{int(item.get('seq') or 0)}",
            str(item.get("op_type_name") or "").strip(),
        ]
        label = " / ".join([part for part in label_parts if part])
        missing_text = "、".join([str(field) for field in item.get("missing_fields") or []]) or "设备/人员"
        messages.append(f"{label} 缺{missing_text}")
    return "；".join(messages)


def raise_no_actionable_schedule_error(
    validation_errors: Optional[List[str]] = None,
    *,
    operations: Optional[List[Any]] = None,
    missing_internal_resource_op_ids: Optional[Set[int]] = None,
) -> None:
    exc = ValidationError("优化结果未生成有效可落库排程行", field="schedule")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "no_actionable_schedule_rows"
    if validation_errors:
        exc.details["validation_errors"] = list(validation_errors)

    missing_samples = _missing_internal_resource_samples(operations, missing_internal_resource_op_ids)
    if missing_samples:
        total = len(missing_samples)
        sample_text = _format_missing_internal_resource_sample(missing_samples)
        suffix = f"；还有 {max(total - 10, 0)} 条未展示" if total > 10 else ""
        exc.details["missing_internal_resource_count"] = int(total)
        exc.details["missing_internal_resource_ops"] = missing_samples[:10]
        exc.details["user_message"] = (
            f"本次排产没有生成可保存结果，存在内部工序缺设备/人员："
            f"{sample_text}{suffix}。请先到批次工序补充页补齐后重试。"
        )
    raise exc


__all__ = ["raise_no_actionable_schedule_error"]
