from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, List, Optional

import pytest

import core.algorithms.greedy.dispatch.sgs as sgs_module
import core.algorithms.greedy.dispatch.sgs_scoring as sgs_scoring_module
from core.algorithms import GreedyScheduler
from core.algorithms.greedy.internal_slot import (
    validate_internal_hours_for_mode as original_validate_internal_hours_for_mode,
)
from core.infrastructure.errors import ValidationError


@dataclass
class _Calendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _batch(batch_id: str) -> Any:
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date="2026-01-02",
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )


def _internal_op(op_id: int, batch_id: str, setup_hours: float) -> Any:
    return SimpleNamespace(
        id=op_id,
        op_code=f"OP{op_id}",
        batch_id=batch_id,
        seq=1,
        source="internal",
        machine_id=f"M{op_id}",
        operator_id=f"O{op_id}",
        setup_hours=setup_hours,
        unit_hours=0.0,
        op_type_id="OT1",
        op_type_name="车削",
    )


def test_sgs_reuses_successful_total_hours_between_average_and_scoring(monkeypatch) -> None:
    calls: List[int] = []

    def _counting_validate(op: Any, batch: Any, *, strict_mode: bool) -> float:
        calls.append(int(getattr(op, "id", 0) or 0))
        return original_validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)

    monkeypatch.setattr(sgs_module, "validate_internal_hours_for_mode", _counting_validate)
    monkeypatch.setattr(sgs_scoring_module, "validate_internal_hours_for_mode", _counting_validate)

    scheduler = GreedyScheduler(calendar_service=_Calendar())
    operations = [_internal_op(1, "B1", 2.0), _internal_op(2, "B2", 1.0)]
    results, summary, _strategy, _used_params = scheduler.schedule(
        operations=operations,
        batches={"B1": _batch("B1"), "B2": _batch("B2")},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B1", "B2"],
    )

    assert summary.failed_ops == 0
    assert sorted(result.op_id for result in results) == [1, 2]
    assert len(calls) == 2
    assert sorted(calls) == [1, 2]


def test_sgs_graph_score_does_not_disable_total_hours_cache(monkeypatch) -> None:
    calls: List[int] = []

    def _counting_validate(op: Any, batch: Any, *, strict_mode: bool) -> float:
        calls.append(int(getattr(op, "id", 0) or 0))
        return original_validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)

    monkeypatch.setattr(sgs_module, "validate_internal_hours_for_mode", _counting_validate)
    monkeypatch.setattr(sgs_scoring_module, "validate_internal_hours_for_mode", _counting_validate)

    scheduler = GreedyScheduler(calendar_service=_Calendar())
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: set()},
        "successor_op_ids_by_op_id": {1: set(), 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
        "score_enabled": True,
        "graph_priority_key_by_op_id": {1: (0.0, 0.0), 2: (-100.0, 0.0)},
    }
    results, summary, _strategy, _used_params = scheduler.schedule(
        operations=[_internal_op(1, "B1", 2.0), _internal_op(2, "B2", 1.0)],
        batches={"B1": _batch("B1"), "B2": _batch("B2")},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B1", "B2"],
        graph_ready_context=graph_ready_context,
    )

    assert summary.failed_ops == 0
    assert [result.op_id for result in results] == [2, 1]
    assert len(calls) == 2
    assert sorted(calls) == [1, 2]


def test_sgs_average_does_not_cache_non_positive_or_missing_op_ids() -> None:
    missing_id_op = _internal_op(3, "B1", 5.0)
    delattr(missing_id_op, "id")
    bool_id_op = _internal_op(4, "B1", 7.0)
    bool_id_op.id = True
    invalid_id_op = _internal_op(5, "B1", 11.0)
    invalid_id_op.id = "not-an-id"
    avg_proc_hours, total_hours_by_op_id = sgs_module._average_proc_hours(
        SimpleNamespace(),
        ops_by_batch={"B1": [_internal_op(0, "B1", 1.0), _internal_op(-1, "B1", 2.0), missing_id_op, bool_id_op, invalid_id_op]},
        batches={"B1": _batch("B1")},
        strict_mode=False,
    )

    assert avg_proc_hours == pytest.approx(5.2)
    assert total_hours_by_op_id == {}


@pytest.mark.parametrize(
    ("op_id", "cached_hours_by_op_id"),
    [
        (0, {0: 99.0}),
        (-1, {-1: 99.0}),
        (True, {1: 99.0}),
        (None, {0: 99.0}),
        ("not-an-id", {7: 99.0}),
    ],
)
def test_sgs_scoring_ignores_cache_for_non_positive_or_invalid_op_id(op_id: Any, cached_hours_by_op_id: dict[int, float]) -> None:
    op = _internal_op(7, "B1", 1.0)
    op.id = op_id
    original_cache = dict(cached_hours_by_op_id)

    total_hours = sgs_scoring_module._scoring_total_hours(
        SimpleNamespace(),
        op=op,
        batch=_batch("B1"),
        strict_mode=False,
        total_hours_by_op_id=cached_hours_by_op_id,
        op_id=op_id,
    )

    assert total_hours == 1.0
    assert cached_hours_by_op_id == original_cache


def test_sgs_invalid_total_hours_is_not_cached_or_hidden() -> None:
    scheduler = GreedyScheduler(calendar_service=_Calendar())

    with pytest.raises(ValidationError) as exc_info:
        scheduler.schedule(
            operations=[_internal_op(1, "B1", float("inf"))],
            batches={"B1": _batch("B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            strict_mode=False,
        )

    assert exc_info.value.field == "setup_hours"
