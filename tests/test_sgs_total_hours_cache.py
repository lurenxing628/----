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


def test_sgs_average_does_not_cache_non_positive_or_missing_op_ids() -> None:
    missing_id_op = _internal_op(3, "B1", 5.0)
    delattr(missing_id_op, "id")
    avg_proc_hours, total_hours_by_op_id = sgs_module._average_proc_hours(
        SimpleNamespace(),
        ops_by_batch={"B1": [_internal_op(0, "B1", 1.0), missing_id_op]},
        batches={"B1": _batch("B1")},
        strict_mode=False,
    )

    assert avg_proc_hours == 3.0
    assert total_hours_by_op_id == {}


def test_sgs_scoring_ignores_cache_for_non_positive_op_id() -> None:
    cached_hours_by_op_id = {0: 99.0}

    total_hours = sgs_scoring_module._scoring_total_hours(
        SimpleNamespace(),
        op=_internal_op(0, "B1", 1.0),
        batch=_batch("B1"),
        strict_mode=False,
        total_hours_by_op_id=cached_hours_by_op_id,
        op_id=0,
    )

    assert total_hours == 1.0
    assert cached_hours_by_op_id == {0: 99.0}


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
