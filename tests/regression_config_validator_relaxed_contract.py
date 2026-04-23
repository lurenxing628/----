from __future__ import annotations

from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.config_validator import normalize_preset_snapshot


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
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def test_relaxed_preset_numeric_fields_follow_field_coercion_contract() -> None:
    snap = normalize_preset_snapshot(
        {
            "priority_weight": "abc",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "bad",
            "time_budget_seconds": "0",
            "freeze_window_days": "-3",
        },
        base=_base_snapshot(),
        strict_mode=False,
    )

    assert snap.priority_weight == 0.4
    assert snap.holiday_default_efficiency == 0.8
    assert snap.ortools_time_limit_seconds == 5
    assert snap.time_budget_seconds == 1
    assert snap.freeze_window_days == 0

    counters = snap.degradation_counters or {}
    assert int(counters.get("invalid_number") or 0) >= 2, counters
    assert int(counters.get("number_below_minimum") or 0) >= 3, counters
