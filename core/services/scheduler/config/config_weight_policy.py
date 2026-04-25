from __future__ import annotations

from typing import Any, Tuple

from core.infrastructure.errors import ValidationError

from ..number_utils import parse_finite_float


def _parse_weight(value: Any, *, field: str) -> float:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValidationError(f"“{field}”不能为空", field=field)
    raw = float(parse_finite_float(value, field=field, allow_none=False))
    if raw < 0:
        raise ValidationError(f"“{field}”不能为负数", field=field)
    return raw


def normalize_single_weight(value: Any, *, field: str) -> float:
    raw = _parse_weight(value, field=field)
    normalized = raw / 100.0 if raw > 1.0 else raw
    if normalized > 1.0:
        raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)
    return float(normalized)


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
    raw_pw = _parse_weight(priority_weight, field=priority_field)
    raw_dw = _parse_weight(due_weight, field=due_field)
    raw_rw = _parse_weight(ready_weight, field=ready_field)

    percent_mode = (raw_pw > 1.0) or (raw_dw > 1.0) or (raw_rw > 1.0)
    if percent_mode:
        for raw, field in ((raw_pw, priority_field), (raw_dw, due_field), (raw_rw, ready_field)):
            if 0 < raw < 1:
                raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
            if raw > 100:
                raise ValidationError(f"“{field}”范围不合理（期望 0~100%）", field=field)
        pw = raw_pw / 100.0
        dw = raw_dw / 100.0
        rw = raw_rw / 100.0
    else:
        pw, dw, rw = raw_pw, raw_dw, raw_rw

    for value, field in ((pw, priority_field), (dw, due_field), (rw, ready_field)):
        if value > 1.0:
            raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)

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
