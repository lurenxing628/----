from __future__ import annotations

from typing import Any, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.field_labels import display_field_label
from core.shared.number_utils import parse_finite_float


def _weight_label(field_name: str) -> str:
    return display_field_label(field_name, fallback=field_name) if "_" in str(field_name or "") else str(field_name or "权重")


def _parse_weight(value: Any, *, field_name: str) -> float:
    label = _weight_label(field_name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValidationError(f"“{label}”不能为空", field=field_name)
    try:
        raw = float(parse_finite_float(value, field=label, allow_none=False))
    except ValidationError as exc:
        raise ValidationError(exc.message, field=field_name) from exc
    if raw < 0:
        raise ValidationError(f"“{label}”不能为负数", field=field_name)
    return raw


def _validate_percent_weights(raw_weights: Tuple[float, float, float], field_names: Tuple[str, str, str]) -> None:
    for raw, field_name in zip(raw_weights, field_names):
        if 0 < raw < 1:
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if raw > 100:
            raise ValidationError(f"“{_weight_label(field_name)}”范围不合理（期望 0~100%）", field=field_name)


def _normalize_weight_values(raw_weights: Tuple[float, float, float], field_names: Tuple[str, str, str]) -> Tuple[float, float, float]:
    if any(raw > 1.0 for raw in raw_weights):
        _validate_percent_weights(raw_weights, field_names)
        return tuple(raw / 100.0 for raw in raw_weights)  # type: ignore[return-value]
    return raw_weights


def _validate_normalized_ranges(weights: Tuple[float, float, float], field_names: Tuple[str, str, str]) -> None:
    for value, field_name in zip(weights, field_names):
        if value > 1.0:
            raise ValidationError(f"“{_weight_label(field_name)}”范围不合理（期望 0~1 或 0~100%）", field=field_name)


def normalize_weight_triplet(
    priority_weight: Any,
    due_weight: Any,
    ready_weight: Any,
    *,
    require_sum_1: bool = True,
    priority_field: str = "priority_weight",
    due_field: str = "due_weight",
    ready_field: str = "ready_weight",
) -> Tuple[float, float, float]:
    field_names = (priority_field, due_field, ready_field)
    raw_weights = (
        _parse_weight(priority_weight, field_name=priority_field),
        _parse_weight(due_weight, field_name=due_field),
        _parse_weight(ready_weight, field_name=ready_field),
    )
    pw, dw, rw = _normalize_weight_values(raw_weights, field_names)
    _validate_normalized_ranges((pw, dw, rw), field_names)

    total = float(pw + dw + rw)
    if require_sum_1 and abs(total - 1.0) > 1e-6:
        raise ValidationError("权重总和应为 1（或 100%）", field="权重")

    return float(pw), float(dw), float(rw)


__all__ = ["normalize_weight_triplet"]
