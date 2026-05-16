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
        graph_analysis_mode="off",
        graph_block_on_cycle="no",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_debug_export="no",
    )


def test_relaxed_preset_numeric_fields_follow_field_coercion_contract() -> None:
    snap = normalize_preset_snapshot(
        {
            "priority_weight": "abc",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "bad",
            "time_budget_seconds": "0",
            "freeze_window_days": "-3",
            "graph_analysis_mode": "bad",
            "graph_block_on_cycle": "maybe",
            "graph_critical_weight": "-1",
            "graph_impact_weight": "bad",
            "graph_debug_export": "maybe",
        },
        base=_base_snapshot(),
        strict_mode=False,
    )

    assert snap.priority_weight == 0.4
    assert snap.holiday_default_efficiency == 0.8
    assert snap.ortools_time_limit_seconds == 5
    assert snap.time_budget_seconds == 1
    assert snap.freeze_window_days == 0
    assert snap.graph_analysis_mode == "off"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_critical_weight == 0
    assert snap.graph_impact_weight == 10
    assert snap.graph_debug_export == "no"

    counters = snap.degradation_counters or {}
    assert int(counters.get("invalid_choice") or 0) >= 3, counters
    assert int(counters.get("invalid_number") or 0) >= 3, counters
    assert int(counters.get("number_below_minimum") or 0) >= 4, counters
    event_messages = " ".join(str(event.get("message") or "") for event in (snap.degradation_events or ()))
    assert "优先级权重" in event_messages
    assert "锁定天数" in event_messages
    assert "priority_weight" not in event_messages
    assert "freeze_window_days" not in event_messages
