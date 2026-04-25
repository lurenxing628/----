from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import core.services.scheduler.schedule_optimizer as schedule_optimizer
from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot


class _StubCalendar:
    pass


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


def _optimize_with_cfg(cfg, *, strict_mode: bool = False):
    return schedule_optimizer.optimize_schedule(
        calendar_service=_StubCalendar(),
        cfg_svc=SimpleNamespace(),
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
        strict_mode=bool(strict_mode),
    )


def _optimize_with_cfg_and_seed(cfg, seed_results, *, strict_mode: bool = False):
    return schedule_optimizer.optimize_schedule(
        calendar_service=_StubCalendar(),
        cfg_svc=SimpleNamespace(),
        cfg=cfg,
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_results=list(seed_results or []),
        resource_pool=None,
        version=1,
        logger=None,
        strict_mode=bool(strict_mode),
    )


def _resolve_params(cfg, *, strict_mode: bool = False):
    return resolve_schedule_params(
        config=cfg,
        strategy=None,
        strategy_params=None,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        dispatch_mode=None,
        dispatch_rule=None,
        resource_pool=None,
        strict_mode=bool(strict_mode),
    )


def _install_stub_scheduler(monkeypatch) -> None:
    class _Scheduler:
        def __init__(self, calendar_service, config_service=None, logger=None):
            self.calendar = calendar_service
            self.config = config_service
            self.logger = logger

        def schedule(
            self,
            operations,
            batches,
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            machine_downtimes=None,
            batch_order_override=None,
            seed_results=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool=None,
        ):
            summary = SimpleNamespace(
                success=True,
                total_ops=int(len(operations or [])),
                scheduled_ops=int(len(operations or [])),
                failed_ops=0,
                warnings=[],
                errors=[],
                duration_seconds=0.0,
            )
            return [], summary, strategy, dict(strategy_params or {})

    monkeypatch.setattr(schedule_optimizer, "GreedyScheduler", _Scheduler)
    monkeypatch.setattr(schedule_optimizer, "_run_ortools_warmstart", lambda **kwargs: kwargs.get("best"))
    monkeypatch.setattr(schedule_optimizer, "_run_local_search", lambda **kwargs: kwargs.get("best"))


def test_optimizer_accepts_raw_dict_cfg(monkeypatch) -> None:
    _install_stub_scheduler(monkeypatch)
    outcome = _optimize_with_cfg({"objective": " MIN_OVERDUE "})
    assert outcome.objective_name == "min_overdue"


def test_optimizer_accepts_plain_object_cfg(monkeypatch) -> None:
    _install_stub_scheduler(monkeypatch)
    outcome = _optimize_with_cfg(SimpleNamespace(objective=" min_overdue "))
    assert outcome.objective_name == "min_overdue"


def test_optimizer_accepts_schedule_config_snapshot(monkeypatch) -> None:
    _install_stub_scheduler(monkeypatch)
    outcome = _optimize_with_cfg(_build_snapshot(objective="min_weighted_tardiness"))
    assert outcome.objective_name == "min_weighted_tardiness"


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "sort_strategy": "priority_first",
            "priority_weight": "   ",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "objective": "min_overdue",
        },
        SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight="   ",
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            objective="min_overdue",
        ),
        _build_snapshot(
            sort_strategy="priority_first",
            priority_weight="   ",
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            objective="min_overdue",
        ),
    ],
)
def test_optimizer_strict_mode_rejects_blank_numeric_for_all_cfg_shapes(monkeypatch, cfg) -> None:
    _install_stub_scheduler(monkeypatch)
    with pytest.raises(ValidationError) as exc_info:
        _optimize_with_cfg(cfg, strict_mode=True)
    assert exc_info.value.field == "priority_weight"


def test_optimizer_strict_config_validation_precedes_invalid_seed_results(monkeypatch) -> None:
    _install_stub_scheduler(monkeypatch)

    with pytest.raises(ValidationError) as exc_info:
        _optimize_with_cfg_and_seed(
            {"priority_weight": "   "},
            [{"op_id": 1, "start_time": None, "end_time": None}, "bad-item"],
            strict_mode=True,
        )

    assert exc_info.value.field == "priority_weight"


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "sort_strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "objective": "min_overdue",
            "time_budget_seconds": "   ",
        },
        SimpleNamespace(
            sort_strategy="priority_first",
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            objective="min_overdue",
            time_budget_seconds="   ",
        ),
    ],
)
def test_optimizer_strict_mode_rejects_blank_numeric_on_raw_cfg(monkeypatch, cfg) -> None:
    _install_stub_scheduler(monkeypatch)
    with pytest.raises(ValidationError) as exc_info:
        _optimize_with_cfg(cfg, strict_mode=True)
    assert exc_info.value.field == "time_budget_seconds"


@pytest.mark.parametrize(
    "cfg",
    [
        {"objective": "not-valid"},
        SimpleNamespace(objective="not-valid"),
    ],
)
def test_optimizer_strict_mode_rejects_invalid_choice_on_raw_cfg(monkeypatch, cfg) -> None:
    _install_stub_scheduler(monkeypatch)
    with pytest.raises(ValidationError) as exc_info:
        _optimize_with_cfg(cfg, strict_mode=True)
    assert exc_info.value.field == "objective"


def test_schedule_params_rejects_invalid_snapshot_sort_strategy_in_strict_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _resolve_params(_build_snapshot(sort_strategy="bad_strategy"), strict_mode=True)
    assert exc_info.value.field == "sort_strategy"


def test_schedule_params_rejects_invalid_snapshot_dispatch_mode_in_strict_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _resolve_params(_build_snapshot(dispatch_mode="bad_mode"), strict_mode=True)
    assert exc_info.value.field == "dispatch_mode"


def test_ensure_schedule_config_snapshot_preserves_existing_degradation_metadata() -> None:
    snapshot = _build_snapshot(
        degradation_events=(
            {
                "code": "invalid_choice",
                "scope": "scheduler.config_snapshot",
                "field": "objective",
                "message": "objective defaulted to min_overdue",
                "count": 2,
                "sample": "bad-objective",
            },
        ),
        degradation_counters={"invalid_choice": 2},
    )

    normalized = ensure_schedule_config_snapshot(
        snapshot,
        strict_mode=False,
        source="tests.snapshot_contract",
    )

    assert tuple(normalized.degradation_events) == tuple(snapshot.degradation_events)
    assert normalized.degradation_counters == {"invalid_choice": 2}
