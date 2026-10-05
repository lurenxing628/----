"""Service-facing labels for the common weight arithmetic."""

from __future__ import annotations

from typing import Any, Tuple

from core.models.schedule_config_runtime_weights import (
    derive_ready_weight_from_priority_due,
    normalize_single_weight,
)
from core.models.schedule_config_runtime_weights import (
    normalize_weight_triplet as normalize_runtime_weights,
)


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
    return normalize_runtime_weights(
        priority_weight, due_weight, ready_weight, require_sum_1=require_sum_1,
        priority_field=priority_field, due_field=due_field, ready_field=ready_field,
    )


__all__ = ["derive_ready_weight_from_priority_due", "normalize_single_weight", "normalize_weight_triplet"]
