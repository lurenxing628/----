from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import core.services.scheduler.run.schedule_optimizer as schedule_optimizer_module
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.run.schedule_optimizer import optimize_schedule


@dataclass
class _Calendar:
    raise_on_midnight: bool = False

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None):
        if self.raise_on_midnight and dt.hour == 0 and dt.minute == 0:
            raise RuntimeError("日历服务暂时不可用")
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


def _batch(batch_id: str, *, due_date=None, ready_date=None, created_at=None):
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date=due_date,
        ready_status="yes",
        ready_date=ready_date,
        created_at=created_at,
        quantity=1,
    )


def _internal_op(batch_id: str):
    return SimpleNamespace(
        id=1,
        op_code=f"OP_{batch_id}",
        batch_id=batch_id,
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT1",
        op_type_name="车削",
    )


def _config(**overrides):
    values = default_snapshot_values()
    values.update(overrides)
    return SimpleNamespace(**values)


def test_schedule_override_full_cover_skips_default_sort_only_for_due_and_created_at():
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_config())
    batch = _batch("B1", due_date="bad-due", ready_date="2026-01-01", created_at="bad-created")

    results, summary, strategy, _params = scheduler.schedule(
        operations=[_internal_op("B1")],
        batches={"B1": batch},
        strategy=SortStrategy.FIFO,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        batch_order_override=["B1"],
        strict_mode=True,
    )

    assert strategy == SortStrategy.FIFO
    assert summary.failed_ops == 0
    assert len(results) == 1


def test_schedule_override_full_cover_still_validates_ready_date():
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_config())
    batch = _batch("B1", due_date="bad-due", ready_date="bad-ready", created_at="bad-created")

    with pytest.raises(ValidationError) as exc_info:
        scheduler.schedule(
            operations=[_internal_op("B1")],
            batches={"B1": batch},
            strategy=SortStrategy.FIFO,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            batch_order_override=["B1"],
            strict_mode=True,
        )

    assert exc_info.value.field == "ready_date"


def test_schedule_created_at_strict_only_applies_to_fifo():
    batch = _batch("B1", due_date="2026-01-02", ready_date=None, created_at="bad-created")

    non_fifo_scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_config())
    results, summary, _strategy, _params = non_fifo_scheduler.schedule(
        operations=[_internal_op("B1")],
        batches={"B1": batch},
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        strict_mode=True,
    )
    assert summary.failed_ops == 0
    assert len(results) == 1

    fifo_scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_config())
    with pytest.raises(ValidationError) as exc_info:
        fifo_scheduler.schedule(
            operations=[_internal_op("B1")],
            batches={"B1": batch},
            strategy=SortStrategy.FIFO,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            strict_mode=True,
        )
    assert exc_info.value.field == "created_at"


@pytest.mark.parametrize("strict_mode", [False, True])
def test_ready_date_adjust_errors_bubble_without_silent_fallback(strict_mode: bool):
    scheduler = GreedyScheduler(calendar_service=_Calendar(raise_on_midnight=True), config_service=_config())
    batch = _batch("B1", due_date="2026-01-02", ready_date="2026-01-03", created_at=None)

    with pytest.raises(RuntimeError, match="日历服务暂时不可用"):
        scheduler.schedule(
            operations=[],
            batches={"B1": batch},
            strategy=SortStrategy.PRIORITY_FIRST,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            strict_mode=strict_mode,
        )


def test_optimize_schedule_created_at_strict_only_for_current_strategy(monkeypatch):
    class _RecordingScheduler:
        def __init__(self, calendar_service, config_service=None, logger=None):
            self.calendar = calendar_service
            self.config = config_service
            self.logger = logger
            self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

        def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
            summary = SimpleNamespace(
                success=True,
                total_ops=0,
                scheduled_ops=0,
                failed_ops=0,
                warnings=[],
                errors=[],
                duration_seconds=0.0,
            )
            return [], summary, strategy, dict(strategy_params or {})

    monkeypatch.setattr(schedule_optimizer_module, "GreedyScheduler", _RecordingScheduler)
    monkeypatch.setattr(schedule_optimizer_module, "_run_ortools_warmstart", lambda **kwargs: kwargs.get("best"))
    monkeypatch.setattr(schedule_optimizer_module, "_run_local_search", lambda **kwargs: kwargs.get("best"))

    cfg_svc = SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "fifo"),
        VALID_DISPATCH_MODES=("batch_order",),
        VALID_DISPATCH_RULES=("slack",),
    )
    batches = {" B1 ": _batch("B1_OBJ", due_date="2026-01-02", ready_date=None, created_at="bad-created")}

    outcome = optimize_schedule(
        calendar_service=_Calendar(),
        cfg_svc=cfg_svc,
        cfg=_config(
            sort_strategy="priority_first",
            algo_mode="greedy",
            objective="min_overdue",
            time_budget_seconds=1,
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            ortools_enabled="no",
        ),
        algo_ops_to_schedule=[],
        batches=batches,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=1,
        logger=None,
        strict_mode=True,
    )
    assert outcome.best_order == ["B1"]

    with pytest.raises(ValidationError) as exc_info:
        optimize_schedule(
            calendar_service=_Calendar(),
            cfg_svc=cfg_svc,
            cfg=_config(
                sort_strategy="fifo",
                algo_mode="greedy",
                objective="min_overdue",
                time_budget_seconds=1,
                dispatch_mode="batch_order",
                dispatch_rule="slack",
                ortools_enabled="no",
            ),
            algo_ops_to_schedule=[],
            batches=batches,
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=1,
            logger=None,
            strict_mode=True,
        )
    assert exc_info.value.field == "created_at"
