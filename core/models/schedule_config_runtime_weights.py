from __future__ import annotations

from typing import Any, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.number_utils import parse_finite_float


def _parse_weight(value: Any, *, field_name: str) -> float:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValidationError(f"“{field_name}”不能为空", field=field_name)
    raw = float(parse_finite_float(value, field=field_name, allow_none=False))
    if raw < 0:
        raise ValidationError(f"“{field_name}”不能为负数", field=field_name)
    return raw


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
    raw_pw = _parse_weight(priority_weight, field_name=priority_field)
    raw_dw = _parse_weight(due_weight, field_name=due_field)
    raw_rw = _parse_weight(ready_weight, field_name=ready_field)

    percent_mode = (raw_pw > 1.0) or (raw_dw > 1.0) or (raw_rw > 1.0)
    if percent_mode:
        for raw, field_name in ((raw_pw, priority_field), (raw_dw, due_field), (raw_rw, ready_field)):
            if 0 < raw < 1:
                raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
            if raw > 100:
                raise ValidationError(f"“{field_name}”范围不合理（期望 0~100%）", field=field_name)
        pw = raw_pw / 100.0
        dw = raw_dw / 100.0
        rw = raw_rw / 100.0
    else:
        pw, dw, rw = raw_pw, raw_dw, raw_rw

    for value, field_name in ((pw, priority_field), (dw, due_field), (rw, ready_field)):
        if value > 1.0:
            raise ValidationError(f"“{field_name}”范围不合理（期望 0~1 或 0~100%）", field=field_name)

    total = float(pw + dw + rw)
    if require_sum_1 and abs(total - 1.0) > 1e-6:
        raise ValidationError("权重总和应为 1（或 100%）", field="权重")

    return float(pw), float(dw), float(rw)


__all__ = ["normalize_weight_triplet"]
