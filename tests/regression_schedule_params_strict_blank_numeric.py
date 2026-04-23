from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.infrastructure.errors import ValidationError


def test_schedule_params_strict_blank_weight_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config=SimpleNamespace(
                sort_strategy="weighted",
                priority_weight="   ",
                due_weight=0.5,
                dispatch_mode="batch_order",
                dispatch_rule="slack",
                auto_assign_enabled="no",
            ),
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


def test_schedule_params_partial_weighted_strategy_params_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config=SimpleNamespace(
                sort_strategy="weighted",
                priority_weight=0.4,
                due_weight=0.5,
                dispatch_mode="batch_order",
                dispatch_rule="slack",
                auto_assign_enabled="no",
            ),
            strategy=None,
            strategy_params={"priority_weight": 0.7},
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=False,
        )

    assert exc_info.value.field == "due_weight", f"partial weighted strategy_params 未定位到 due_weight：{exc_info.value.field!r}"
