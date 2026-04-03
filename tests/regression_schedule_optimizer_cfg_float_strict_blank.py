from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_optimizer import optimize_schedule


class _StubCalendar:
    pass


@pytest.mark.parametrize(
    ("field_name", "cfg_kwargs"),
    [
        (
            "priority_weight",
            {
                "sort_strategy": "weighted",
                "priority_weight": "   ",
                "due_weight": 0.5,
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": 20,
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "ortools_enabled": "no",
            },
        ),
        (
            "time_budget_seconds",
            {
                "sort_strategy": "priority_first",
                "priority_weight": 0.4,
                "due_weight": 0.5,
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "   ",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "ortools_enabled": "no",
            },
        ),
    ],
)
def test_schedule_optimizer_strict_blank_numeric_rejected(field_name: str, cfg_kwargs) -> None:
    cfg = SimpleNamespace(**cfg_kwargs)
    cfg_svc = SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "weighted"),
        VALID_DISPATCH_MODES=("batch_order", "sgs"),
        VALID_DISPATCH_RULES=("slack", "cr", "atc"),
    )

    with pytest.raises(ValidationError) as exc_info:
        optimize_schedule(
            calendar_service=_StubCalendar(),
            cfg_svc=cfg_svc,
            cfg=cfg,
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=1,
            logger=None,
            strict_mode=True,
        )

    assert exc_info.value.field == field_name, f"strict_mode 数值空白应定位到字段 {field_name!r}"
