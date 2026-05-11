from __future__ import annotations

from typing import Any, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.field_labels import display_field_label

from ..number_utils import parse_finite_float


def _weight_label(field: str) -> str:
    return display_field_label(field, fallback=field) if "_" in str(field or "") else str(field or "权重")


def _parse_weight(value: Any, *, field: str) -> float:
    label = _weight_label(field)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValidationError(f"“{label}”不能为空", field=field)
    try:
        raw = float(parse_finite_float(value, field=label, allow_none=False))
    except ValidationError as exc:
        raise ValidationError(exc.message, field=field) from exc
    if raw < 0:
        raise ValidationError(f"“{label}”不能为负数", field=field)
    return raw


def normalize_single_weight(value: Any, *, field: str) -> float:
    raw = _parse_weight(value, field=field)
    normalized = raw / 100.0 if raw > 1.0 else raw
    if normalized > 1.0:
        raise ValidationError(f"“{_weight_label(field)}”范围不合理（期望 0~1 或 0~100%）", field=field)
    return float(normalized)


def _validate_percent_weights(raw_weights: Tuple[float, float, float], fields: Tuple[str, str, str]) -> None:
    for raw, field in zip(raw_weights, fields):
        if 0 < raw < 1:
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if raw > 100:
            raise ValidationError(f"“{_weight_label(field)}”范围不合理（期望 0~100%）", field=field)


def _normalize_weight_values(raw_weights: Tuple[float, float, float], fields: Tuple[str, str, str]) -> Tuple[float, float, float]:
    if any(raw > 1.0 for raw in raw_weights):
        _validate_percent_weights(raw_weights, fields)
        return tuple(raw / 100.0 for raw in raw_weights)  # type: ignore[return-value]
    return raw_weights


def _validate_normalized_ranges(weights: Tuple[float, float, float], fields: Tuple[str, str, str]) -> None:
    for value, field in zip(weights, fields):
        if value > 1.0:
            raise ValidationError(f"“{_weight_label(field)}”范围不合理（期望 0~1 或 0~100%）", field=field)


def normalize_weight_triplet(
    priority_weight: Any,
    due_weight: Any,
    ready_weight: Any,
    *,
    require_sum_1: bool = True,
    priority_field: str = "优先级权重",
    due_field: str = "交期权重",
    ready_field: str = "齐套权重",
) -> Tuple[float, float, float]:
    fields = (priority_field, due_field, ready_field)
    raw_weights = (
        _parse_weight(priority_weight, field=priority_field),
        _parse_weight(due_weight, field=due_field),
        _parse_weight(ready_weight, field=ready_field),
    )
    pw, dw, rw = _normalize_weight_values(raw_weights, fields)
    _validate_normalized_ranges((pw, dw, rw), fields)

    total = float(pw + dw + rw)
    if require_sum_1 and abs(total - 1.0) > 1e-6:
        raise ValidationError("权重总和应为 1（或 100%）", field="权重")

    return float(pw), float(dw), float(rw)


def derive_ready_weight_from_priority_due(
    priority_weight: Any,
    due_weight: Any,
    *,
    priority_field: str = "优先级权重",
    due_field: str = "交期权重",
) -> Tuple[float, float, float]:
    raw_pw = _parse_weight(priority_weight, field=priority_field)
    raw_dw = _parse_weight(due_weight, field=due_field)
    percent_mode = float(raw_pw) > 1.0 or float(raw_dw) > 1.0
    raw_total = float(raw_pw) + float(raw_dw)
    raw_ready = (100.0 - raw_total) if percent_mode else (1.0 - raw_total)
    if raw_ready < -1e-9:
        raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
    return normalize_weight_triplet(
        raw_pw,
        raw_dw,
        max(0.0, float(raw_ready)),
        require_sum_1=True,
        priority_field=priority_field,
        due_field=due_field,
    )


__all__ = [
    "derive_ready_weight_from_priority_due",
    "normalize_single_weight",
    "normalize_weight_triplet",
]
