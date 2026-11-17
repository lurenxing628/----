from __future__ import annotations

from typing import Tuple

from core.errors import ValidationError

# (配置键, 页面字段名)：单项错误归属配置键，提示用页面字段名；合计类错误没有对应单键，归属“权重”。
_WEIGHT_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("priority_weight", "优先级权重"),
    ("due_weight", "交期权重"),
    ("ready_weight", "齐套权重"),
)


def _validate_percent_weights(raw_weights: Tuple[float, float, float]) -> None:
    for raw, (key, label) in zip(raw_weights, _WEIGHT_FIELDS):
        if 0 < raw < 1:
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if raw > 100:
            raise ValidationError(f"“{label}”范围不合理（期望 0~100%）", field=key)


def _normalize_weight_values(raw_weights: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if any(raw > 1.0 for raw in raw_weights):
        _validate_percent_weights(raw_weights)
        return tuple(raw / 100.0 for raw in raw_weights)  # type: ignore[return-value]
    return raw_weights


def normalize_weight_triplet(
    priority_weight: float,
    due_weight: float,
    ready_weight: float,
) -> Tuple[float, float, float]:
    """The three coerced weights (coerce_config_field admits each as a float >= 0), as fractions summing to 1."""
    pw, dw, rw = _normalize_weight_values((priority_weight, due_weight, ready_weight))
    if abs(pw + dw + rw - 1.0) > 1e-6:
        raise ValidationError("权重总和应为 1（或 100%）", field="权重")
    return pw, dw, rw


__all__ = ["normalize_weight_triplet"]
