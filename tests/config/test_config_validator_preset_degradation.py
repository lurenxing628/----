"""回归测试：normalize_preset_snapshot 在非严格模式下把越界/非法/空白的预设字段降级回 base 值并记 degradation_events 与按类计数（number_below_minimum/invalid_number/invalid_choice/blank_required），消息只暴露中文字段名不泄露内部 key；严格模式下空白与非法数字改抛带正确 field 的 ValidationError，但整体缺省（{}）仍允许。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.config.config_validator import normalize_preset_snapshot


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


def test_config_validator_preset_degradation_and_min_clamp() -> None:
    snap = normalize_preset_snapshot(
        {
            "priority_weight": "-1",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "0",
            "time_budget_seconds": "-5",
            "freeze_window_days": "-3",
            "graph_analysis_mode": "bad",
            "graph_block_on_cycle": "maybe",
            "graph_critical_weight": "-1",
            "graph_impact_weight": "bad",
            "graph_debug_export": "maybe",
        },
        base=_base_snapshot(),
    )

    assert snap.priority_weight == 0.4
    assert snap.holiday_default_efficiency == 0.8
    assert snap.ortools_time_limit_seconds == 1
    assert snap.time_budget_seconds == 1
    assert snap.freeze_window_days == 0
    assert snap.graph_analysis_mode == "off"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_critical_weight == 0
    assert snap.graph_impact_weight == 10
    assert snap.graph_debug_export == "no"

    event_fields = {str(event.get("field") or "") for event in (snap.degradation_events or ())}
    assert {
        "priority_weight",
        "holiday_default_efficiency",
        "ortools_time_limit_seconds",
        "time_budget_seconds",
        "freeze_window_days",
        "graph_analysis_mode",
        "graph_block_on_cycle",
        "graph_critical_weight",
        "graph_impact_weight",
        "graph_debug_export",
    }.issubset(event_fields)

    counters = snap.degradation_counters or {}
    assert int(counters.get("number_below_minimum") or 0) == 6
    assert int(counters.get("invalid_number") or 0) == 1
    assert int(counters.get("invalid_choice") or 0) == 3
    event_messages = " ".join(str(event.get("message") or "") for event in (snap.degradation_events or ()))
    assert "优先级权重" in event_messages
    assert "锁定天数" in event_messages
    assert "priority_weight" not in event_messages
    assert "freeze_window_days" not in event_messages


def test_config_validator_preset_strict_blank_rejected_but_missing_allowed() -> None:
    base = _base_snapshot()

    snap = normalize_preset_snapshot(
        {},
        base=base,
        strict_mode=True,
    )
    assert snap.dispatch_mode == base.dispatch_mode
    assert snap.dispatch_rule == base.dispatch_rule
    assert snap.auto_assign_enabled == base.auto_assign_enabled

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"sort_strategy": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "sort_strategy"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"dispatch_mode": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "dispatch_mode"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"dispatch_rule": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "dispatch_rule"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"auto_assign_enabled": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "auto_assign_enabled"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"algo_mode": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "algo_mode"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"objective": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "objective"

    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"graph_analysis_mode": "   "},
            base=base,
            strict_mode=True,
        )
    assert exc_info.value.field == "graph_analysis_mode"


def test_config_validator_preset_relaxed_invalid_numeric_falls_back_with_degradation() -> None:
    snap = normalize_preset_snapshot(
        {"priority_weight": "abc"},
        base=_base_snapshot(),
    )

    assert snap.priority_weight == 0.4
    counters = snap.degradation_counters or {}
    assert int(counters.get("invalid_number") or 0) == 1, counters
    event_messages = " ".join(str(event.get("message") or "") for event in (snap.degradation_events or ()))
    assert "优先级权重" in event_messages
    assert "priority_weight" not in event_messages


def test_config_validator_preset_strict_invalid_numeric_still_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        normalize_preset_snapshot(
            {"priority_weight": "abc"},
            base=_base_snapshot(),
            strict_mode=True,
        )

    assert exc_info.value.field == "priority_weight"
    assert "优先级权重" in exc_info.value.message
    assert "priority_weight" not in exc_info.value.message


def test_config_validator_preset_relaxed_invalid_choice_and_yesno_are_observable() -> None:
    snap = normalize_preset_snapshot(
        {
            "sort_strategy": "bad_strategy",
            "dispatch_mode": "bad_mode",
            "auto_assign_enabled": "maybe",
            "graph_analysis_mode": "bad",
            "graph_block_on_cycle": "maybe",
            "graph_debug_export": "maybe",
        },
        base=_base_snapshot(),
    )

    assert snap.sort_strategy == "priority_first"
    assert snap.dispatch_mode == "batch_order"
    assert snap.auto_assign_enabled == "no"
    assert snap.graph_analysis_mode == "off"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_debug_export == "no"
    counters = snap.degradation_counters or {}
    assert int(counters.get("invalid_choice") or 0) == 6, counters


def test_config_validator_preset_relaxed_blank_choice_and_yesno_emit_blank_required() -> None:
    snap = normalize_preset_snapshot(
        {
            "dispatch_rule": "   ",
            "freeze_window_enabled": None,
            "graph_analysis_mode": "   ",
            "graph_debug_export": None,
        },
        base=_base_snapshot(),
    )

    assert snap.dispatch_rule == "slack"
    assert snap.freeze_window_enabled == "no"
    assert snap.graph_analysis_mode == "off"
    assert snap.graph_debug_export == "no"
    counters = snap.degradation_counters or {}
    assert int(counters.get("blank_required") or 0) == 4, counters


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
