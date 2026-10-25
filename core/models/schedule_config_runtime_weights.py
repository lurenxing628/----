from __future__ import annotations

from typing import Any, Tuple

from core.errors import ValidationError
from core.shared.strict_parse import parse_required_float

_WEIGHT_FIELDS: Tuple[str, str, str] = ("优先级权重", "交期权重", "齐套权重")


def _parse_weight(value: Any, *, field_name: str) -> float:
    raw = parse_required_float(value, field=field_name)
    if raw < 0:
        raise ValidationError(f"“{field_name}”不能为负数", field=field_name)
    return raw


def _validate_percent_weights(raw_weights: Tuple[float, float, float]) -> None:
    for raw, field_name in zip(raw_weights, _WEIGHT_FIELDS):
        if 0 < raw < 1:
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if raw > 100:
            raise ValidationError(f"“{field_name}”范围不合理（期望 0~100%）", field=field_name)


def _normalize_weight_values(raw_weights: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if any(raw > 1.0 for raw in raw_weights):
        _validate_percent_weights(raw_weights)
        return tuple(raw / 100.0 for raw in raw_weights)  # type: ignore[return-value]
    return raw_weights


def normalize_weight_triplet(
    priority_weight: Any,
    due_weight: Any,
    ready_weight: Any,
) -> Tuple[float, float, float]:
    raw_weights = (
        _parse_weight(priority_weight, field_name=_WEIGHT_FIELDS[0]),
        _parse_weight(due_weight, field_name=_WEIGHT_FIELDS[1]),
        _parse_weight(ready_weight, field_name=_WEIGHT_FIELDS[2]),
    )
    pw, dw, rw = _normalize_weight_values(raw_weights)

    total = float(pw + dw + rw)
    if abs(total - 1.0) > 1e-6:
        raise ValidationError("权重总和应为 1（或 100%）", field="权重")

    return float(pw), float(dw), float(rw)


__all__ = ["normalize_weight_triplet"]
