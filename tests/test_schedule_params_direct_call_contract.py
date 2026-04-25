from __future__ import annotations

from datetime import datetime

import pytest

from core.algorithms.dispatch_rules import DispatchRule
from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot


def _call_params(*, config, strategy=None, strategy_params=None, strict_mode=False, algo_stats=None):
    return resolve_schedule_params(
        config=config,
        strategy=strategy,
        strategy_params=strategy_params,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        dispatch_mode=None,
        dispatch_rule=None,
        resource_pool=None,
        algo_stats=algo_stats,
        strict_mode=bool(strict_mode),
    )


def _build_snapshot(**overrides) -> ScheduleConfigSnapshot:
    data = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }
    data.update(overrides)
    return ScheduleConfigSnapshot(**data)


def test_schedule_params_allows_missing_runtime_config_in_non_strict_direct_call() -> None:
    params = _call_params(config=None, strict_mode=False)

    assert params.strategy == SortStrategy.PRIORITY_FIRST
    assert params.dispatch_mode_key == "batch_order"
    assert params.dispatch_rule_enum == DispatchRule.SLACK
    assert params.auto_assign_enabled is False


def test_schedule_params_rejects_missing_runtime_config_in_strict_direct_call() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _call_params(config=None, strict_mode=True)

    assert exc_info.value.field == "sort_strategy"


def test_schedule_params_raw_dict_nonstrict_choice_fallback_is_visible() -> None:
    algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    params = _call_params(
        config={"sort_strategy": "bad-strategy"},
        strict_mode=False,
        algo_stats=algo_stats,
    )

    assert params.strategy == SortStrategy.PRIORITY_FIRST
    assert any("排序策略" in warning for warning in params.warnings), params.warnings
    assert not any("sort_strategy" in warning for warning in params.warnings), params.warnings
    assert int((algo_stats.get("param_fallbacks") or {}).get("sort_strategy_defaulted_count") or 0) == 1


def test_schedule_params_snapshot_nonstrict_choice_fallback_is_visible() -> None:
    algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    params = _call_params(
        config=_build_snapshot(sort_strategy="bad-strategy"),
        strict_mode=False,
        algo_stats=algo_stats,
    )

    assert params.strategy == SortStrategy.PRIORITY_FIRST
    assert any("排序策略" in warning for warning in params.warnings), params.warnings
    assert not any("sort_strategy" in warning for warning in params.warnings), params.warnings
    assert int((algo_stats.get("param_fallbacks") or {}).get("sort_strategy_defaulted_count") or 0) == 1


def test_schedule_params_raw_dict_strict_mode_rejects_consumed_invalid_choice() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _call_params(
            config={"sort_strategy": "bad-strategy"},
            strict_mode=True,
        )

    assert exc_info.value.field == "sort_strategy"


def test_schedule_params_snapshot_strict_mode_ignores_unconsumed_invalid_choice() -> None:
    params = _call_params(
        config=_build_snapshot(objective="not-valid"),
        strict_mode=True,
    )

    assert params.strategy == SortStrategy.PRIORITY_FIRST
    assert params.dispatch_mode_key == "batch_order"
    assert params.dispatch_rule_enum == DispatchRule.SLACK
    assert params.auto_assign_enabled is False


def test_schedule_params_weighted_override_invalid_values_fallback_in_non_strict_mode() -> None:
    algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    params = _call_params(
        config=None,
        strategy=SortStrategy.WEIGHTED,
        strategy_params={"priority_weight": None, "due_weight": "abc"},
        strict_mode=False,
        algo_stats=algo_stats,
    )

    assert params.used_params["priority_weight"] == pytest.approx(0.4)
    assert params.used_params["due_weight"] == pytest.approx(0.5)
    assert any("优先级权重" in warning for warning in params.warnings), params.warnings
    assert any("交期权重" in warning for warning in params.warnings), params.warnings
    assert not any("priority_weight" in warning or "due_weight" in warning for warning in params.warnings), params.warnings
    assert int((algo_stats.get("param_fallbacks") or {}).get("weighted_priority_weight_defaulted_count") or 0) == 1
    assert int((algo_stats.get("param_fallbacks") or {}).get("weighted_due_weight_defaulted_count") or 0) == 1


def test_schedule_params_weighted_override_invalid_values_rejected_in_strict_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _call_params(
            config=None,
            strategy=SortStrategy.WEIGHTED,
            strategy_params={"priority_weight": None, "due_weight": "abc"},
            strict_mode=True,
        )

    assert exc_info.value.field == "priority_weight"


def test_schedule_params_strict_mode_rejects_invalid_start_dt() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config=_build_snapshot(),
            strategy=None,
            strategy_params=None,
            start_dt="not-a-datetime",
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool=None,
            algo_stats=None,
            strict_mode=True,
        )

    assert exc_info.value.field == "start_dt"


def test_schedule_params_strict_mode_rejects_invalid_end_date() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config=_build_snapshot(),
            strategy=None,
            strategy_params=None,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            end_date="not-a-date",
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool=None,
            algo_stats=None,
            strict_mode=True,
        )

    assert exc_info.value.field == "end_date"
