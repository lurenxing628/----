from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest

from core.algorithms.greedy import auto_assign as auto_assign_module
from core.algorithms.greedy.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.infrastructure.errors import ValidationError


@dataclass
class _Calendar:
    efficiency: float = 1.0

    def __post_init__(self) -> None:
        self.adjust_calls = []

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None):
        self.adjust_calls.append((dt, priority, operator_id))
        if dt.minute:
            return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None):
        return self.efficiency

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


def _build_internal_entities(**op_overrides):
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="车削",
    )
    batch = SimpleNamespace(
        batch_id="B1",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    for key, value in op_overrides.items():
        if key.startswith("batch_"):
            setattr(batch, key[len("batch_") :], value)
        else:
            setattr(op, key, value)
    return op, batch


def test_estimator_matches_schedule_internal_and_is_read_only():
    calendar = _Calendar()
    scheduler = GreedyScheduler(calendar_service=calendar)
    op, batch = _build_internal_entities()
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    machine_timeline = {"M1": [(base_time, base_time + timedelta(hours=2))]}
    operator_timeline = {"O1": [(base_time + timedelta(hours=2), base_time + timedelta(hours=3))]}
    downtime_segments = [(base_time + timedelta(hours=3), base_time + timedelta(hours=4))]

    machine_before = list(machine_timeline["M1"])
    operator_before = list(operator_timeline["O1"])
    downtime_before = list(downtime_segments)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=machine_timeline["M1"],
        operator_timeline=operator_timeline["O1"],
        end_dt_exclusive=None,
        machine_downtimes=downtime_segments,
        last_op_type_by_machine={"M1": "铣削"},
        abort_after=None,
    )

    result, blocked = scheduler._schedule_internal(
        op,
        batch,
        {"B1": base_time},
        {"M1": list(machine_before)},
        {"O1": list(operator_before)},
        base_time,
        [],
        None,
        {"M1": list(downtime_before)},
        last_op_type_by_machine={"M1": "铣削"},
        machine_busy_hours={},
        operator_busy_hours={},
    )

    assert blocked is False
    assert result is not None
    assert estimate.start_time == datetime(2026, 1, 1, 12, 0, 0)
    assert estimate.start_time == result.start_time
    assert estimate.end_time == result.end_time
    assert estimate.changeover_penalty == 1
    assert machine_timeline["M1"] == machine_before
    assert operator_timeline["O1"] == operator_before
    assert downtime_segments == downtime_before


def test_estimator_uses_adjusted_max_of_prev_end_and_base_time():
    calendar = _Calendar()
    op, batch = _build_internal_entities()
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    prev_end = datetime(2026, 1, 1, 8, 45, 0)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=prev_end,
        machine_timeline=[],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert calendar.adjust_calls[0][0] == prev_end
    assert estimate.start_time == datetime(2026, 1, 1, 9, 0, 0)


def test_estimator_handles_more_than_two_hundred_fragments():
    calendar = _Calendar()
    op, batch = _build_internal_entities(setup_hours=0.5)
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    machine_segments = []
    current = base_time
    for _ in range(205):
        machine_segments.append((current, current + timedelta(hours=1)))
        current += timedelta(hours=1)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=machine_segments,
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert estimate.start_time == current
    assert estimate.end_time == current + timedelta(minutes=30)


def test_abort_after_only_applies_after_adjustment_and_uses_strict_greater_than():
    calendar = _Calendar()
    op, batch = _build_internal_entities(setup_hours=0.5)
    base_time = datetime(2026, 1, 1, 8, 45, 0)

    hit = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=datetime(2026, 1, 1, 8, 30, 0),
    )
    assert hit.abort_after_hit is True
    assert hit.blocked_by_window is False

    not_hit = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=datetime(2026, 1, 1, 9, 0, 0),
    )
    assert not_hit.abort_after_hit is False
    assert not_hit.start_time == datetime(2026, 1, 1, 9, 0, 0)


def test_validate_internal_hours_keeps_direct_call_compatibility_and_exposes_property_errors():
    op, batch = _build_internal_entities(setup_hours=None, unit_hours="", batch_quantity=False)
    assert validate_internal_hours(op, batch) == 0.0

    op_true, batch_true = _build_internal_entities(setup_hours=True, unit_hours=0.0, batch_quantity=1)
    assert validate_internal_hours(op_true, batch_true) == 1.0

    op_containers, batch_containers = _build_internal_entities(setup_hours=[], unit_hours={}, batch_quantity={})
    assert validate_internal_hours(op_containers, batch_containers) == 0.0

    op_bad, batch_bad = _build_internal_entities(setup_hours="   ", unit_hours=0.0, batch_quantity=1)
    with pytest.raises(ValueError):
        validate_internal_hours(op_bad, batch_bad)

    class _Broken:
        @property
        def setup_hours(self):
            raise AttributeError("runtime failure")

        unit_hours = 0.0
        batch_id = "B1"

    broken_op = _Broken()
    with pytest.raises(AttributeError):
        validate_internal_hours(broken_op, batch_true)


def test_efficiency_fallback_only_updates_formal_schedule_counter():
    calendar = _Calendar(efficiency=None)  # type: ignore[arg-type]
    scheduler = GreedyScheduler(calendar_service=calendar)
    op, batch = _build_internal_entities()
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )
    assert estimate.efficiency_fallback_used is True
    assert scheduler._last_algo_stats.get("fallback_counts", {}).get("internal_efficiency_fallback_count", 0) == 0

    result, blocked = scheduler._schedule_internal(
        op,
        batch,
        {"B1": base_time},
        {},
        {},
        base_time,
        [],
        None,
    )
    assert blocked is False
    assert result is not None
    assert scheduler._last_algo_stats.get("fallback_counts", {}).get("internal_efficiency_fallback_count", 0) == 1


def test_auto_assign_passes_best_end_to_estimator_abort_after():
    calendar = _Calendar()
    scheduler = GreedyScheduler(calendar_service=calendar)
    op, batch = _build_internal_entities(machine_id="", operator_id="", op_type_id="OT1")
    resource_pool = {
        "machines_by_op_type": {"OT1": ["M1", "M2"]},
        "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]},
        "machines_by_operator": {},
        "pair_rank": {},
    }
    recorded_abort_after = []

    def _fake_estimator(**kwargs):
        recorded_abort_after.append(kwargs.get("abort_after"))
        if kwargs["machine_id"] == "M1":
            return SimpleNamespace(
                machine_id="M1",
                operator_id="O1",
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                end_time=datetime(2026, 1, 1, 9, 0, 0),
                total_hours=1.0,
                changeover_penalty=0,
                blocked_by_window=False,
                abort_after_hit=False,
                efficiency_fallback_used=False,
            )
        return SimpleNamespace(
            machine_id="M2",
            operator_id="O2",
            start_time=datetime(2026, 1, 1, 9, 30, 0),
            end_time=datetime(2026, 1, 1, 9, 30, 0),
            total_hours=0.0,
            changeover_penalty=0,
            blocked_by_window=False,
            abort_after_hit=True,
            efficiency_fallback_used=False,
        )

    with mock.patch.object(auto_assign_module, "estimate_internal_slot", side_effect=_fake_estimator):
        chosen = scheduler._auto_assign_internal_resources(
            op=op,
            batch=batch,
            batch_progress={"B1": datetime(2026, 1, 1, 8, 0, 0)},
            machine_timeline={},
            operator_timeline={},
            base_time=datetime(2026, 1, 1, 8, 0, 0),
            end_dt_exclusive=None,
            machine_downtimes={},
            resource_pool=resource_pool,
            last_op_type_by_machine={},
            machine_busy_hours={},
            operator_busy_hours={},
        )

    assert chosen == ("M1", "O1")
    assert recorded_abort_after == [None, datetime(2026, 1, 1, 9, 0, 0)]


def test_zero_hours_returns_start_equals_end():
    calendar = _Calendar()
    op, batch = _build_internal_entities(setup_hours=0.0, unit_hours=0.0)
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert estimate.start_time == base_time
    assert estimate.end_time == base_time
    assert estimate.total_hours == 0.0


def test_zero_hours_still_avoids_occupied_segments():
    calendar = _Calendar()
    op, batch = _build_internal_entities(setup_hours=0.0, unit_hours=0.0)
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[(base_time - timedelta(hours=1), base_time + timedelta(hours=1))],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert estimate.start_time == base_time + timedelta(hours=1)
    assert estimate.end_time == estimate.start_time
    assert estimate.total_hours == 0.0


def test_zero_hours_at_segment_start_does_not_shift():
    calendar = _Calendar()
    op, batch = _build_internal_entities(setup_hours=0.0, unit_hours=0.0)
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=base_time,
        prev_end=base_time,
        machine_timeline=[(base_time, base_time + timedelta(hours=1))],
        operator_timeline=[],
        end_dt_exclusive=None,
        machine_downtimes=[],
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert estimate.start_time == base_time
    assert estimate.end_time == base_time
    assert estimate.total_hours == 0.0


def test_efficiency_edge_cases_none_invalid_values_and_exception():
    op, batch = _build_internal_entities(setup_hours=2.0, unit_hours=0.0)
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    def _estimate(calendar):
        return estimate_internal_slot(
            calendar=calendar,
            op=op,
            batch=batch,
            machine_id="M1",
            operator_id="O1",
            base_time=base_time,
            prev_end=base_time,
            machine_timeline=[],
            operator_timeline=[],
            end_dt_exclusive=None,
            machine_downtimes=[],
            last_op_type_by_machine=None,
            abort_after=None,
        )

    class _NoneEfficiencyCalendar(_Calendar):
        def get_efficiency(self, dt: datetime, operator_id=None):
            return None

    none_estimate = _estimate(_NoneEfficiencyCalendar())
    assert none_estimate.total_hours == 2.0
    assert none_estimate.end_time == base_time + timedelta(hours=2)
    assert none_estimate.efficiency_fallback_used is True

    class _InvalidEfficiencyCalendar(_Calendar):
        def __init__(self, efficiency):
            super().__init__(efficiency=efficiency)

        def get_efficiency(self, dt: datetime, operator_id=None):
            return self.efficiency

    for invalid_efficiency in (0.0, -1.0, float("inf"), float("nan")):
        with pytest.raises(ValidationError) as exc_info:
            _estimate(_InvalidEfficiencyCalendar(invalid_efficiency))

        assert exc_info.value.field == "efficiency"

    class _ExplodingEfficiencyCalendar(_Calendar):
        def get_efficiency(self, dt: datetime, operator_id=None):
            raise RuntimeError("效率读取失败")

    with pytest.raises(RuntimeError, match="效率读取失败"):
        _estimate(_ExplodingEfficiencyCalendar())
