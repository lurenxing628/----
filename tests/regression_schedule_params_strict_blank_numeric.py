from __future__ import annotations

import pytest

from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.infrastructure.errors import ValidationError


def test_schedule_params_strict_blank_weight_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config={
                "sort_strategy": "weighted",
                "priority_weight": "   ",
                "due_weight": 0.5,
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
            },
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        )

    assert exc_info.value.field == "priority_weight", f"strict_mode 权重空白未定位到 priority_weight：{exc_info.value.field!r}"
