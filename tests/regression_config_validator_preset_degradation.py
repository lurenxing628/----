from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.config_validator import normalize_preset_snapshot

VALID_STRATEGIES = ("priority_first", "due_date_first", "weighted", "fifo")
VALID_DISPATCH_MODES = ("batch_order", "sgs")
VALID_DISPATCH_RULES = ("slack", "cr", "atc")
VALID_ALGO_MODES = ("greedy", "improve")
VALID_OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")


def _base_snapshot() -> ScheduleConfigSnapshot:
    return ScheduleConfigSnapshot(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=0.8,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def test_config_validator_preset_degradation_and_min_clamp() -> None:
    snap = normalize_preset_snapshot(
        {
            "priority_weight": "-1",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "0",
            "time_budget_seconds": "-5",
            "freeze_window_days": "-3",
        },
        base=_base_snapshot(),
        valid_strategies=VALID_STRATEGIES,
        valid_dispatch_modes=VALID_DISPATCH_MODES,
        valid_dispatch_rules=VALID_DISPATCH_RULES,
        valid_algo_modes=VALID_ALGO_MODES,
        valid_objectives=VALID_OBJECTIVES,
    )

    assert snap.priority_weight == 0.4
    assert snap.holiday_default_efficiency == 0.8
    assert snap.ortools_time_limit_seconds == 1
    assert snap.time_budget_seconds == 1
    assert snap.freeze_window_days == 0

    event_fields = {str(event.get("field") or "") for event in (snap.degradation_events or ())}
    assert {
        "priority_weight",
        "holiday_default_efficiency",
        "ortools_time_limit_seconds",
        "time_budget_seconds",
        "freeze_window_days",
    }.issubset(event_fields)

    counters = snap.degradation_counters or {}
    assert int(counters.get("number_below_minimum") or 0) == 5


def test_config_validator_preset_still_rejects_malformed_numeric() -> None:
    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"priority_weight": "abc"},
            base=_base_snapshot(),
            valid_strategies=VALID_STRATEGIES,
            valid_dispatch_modes=VALID_DISPATCH_MODES,
            valid_dispatch_rules=VALID_DISPATCH_RULES,
            valid_algo_modes=VALID_ALGO_MODES,
            valid_objectives=VALID_OBJECTIVES,
        )

    assert exc_info.value.field == "priority_weight"
