"""Independent equivalence checks with unmodified SQLite-backed native timing."""

import random
from copy import deepcopy
from datetime import timedelta

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.greedy.scheduler import GreedyScheduler
from tests._support.busy_block_case import (
    BASE,
    at,
    counted_attempts,
    day_row,
    equivalent_slot,
    native_calendar,
    slot_case,
    spans,
)


@pytest.mark.parametrize("segments,expected", [
    (spans((0, 1), (1, 2), (2, 3)), 3),
    (spans((0, 1.5), (1, 2.5), (2, 3)), 3),
    (spans((0, 2), (0.25, 0.5), (0.5, 1), (1, 1.5), (2, 3)), 3),
    (spans((0, 1), (1.25, 2), (2, 3)), 1),
    (spans((0, 1), (1.125, 2), (2, 3)), 3),
    (spans((0, 0), (0, 1), (0.5, 0.25), (1, 2)), 2),
], ids=["touching", "overlap", "nested", "exact-fit-gap", "too-small-gap", "invalid-spans"])
def test_native_interval_shapes_preserve_earliest_gap(segments, expected):
    result, _, _ = equivalent_slot(slot_case(machine=segments))
    assert result.start_time == at(expected)
    assert result.end_time == at(expected + 0.25)
    assert result.changeover_penalty == 1
    assert not result.efficiency_fallback_used


@pytest.mark.parametrize("resource", ["machine", "operator", "downtime"])
def test_dense_native_chain_reduces_estimate_attempts_without_timing_mocks(resource):
    segments = spans(*[(i / 60, (i + 1) / 60) for i in range(180)])
    case = slot_case(hours=1 / 120, **{resource: segments})
    result, old_count, new_count = equivalent_slot(case)
    assert result.start_time == at(3)
    assert result.end_time == at(3) + timedelta(seconds=30)
    assert old_count == 181
    assert new_count == 2


def test_mixed_resource_chain_keeps_gap_and_reduces_attempts():
    case = slot_case(
        machine=spans((0, 1), (1, 2), (2, 3)),
        operator=spans((3, 4), (4, 5)), downtime=spans((5, 6), (6.5, 7)),
    )
    result, old_count, new_count = equivalent_slot(case)
    assert result.start_time == at(6)
    assert result.end_time == at(6.25)
    assert new_count < old_count


@pytest.mark.parametrize("seed", range(24))
def test_seeded_native_random_mixed_segments_and_calendar_policies(seed):
    rng = random.Random(910000 + seed)
    rows = [day_row(
        day, shift_start=rng.choice(("06:00", "08:00", "10:00")), shift_end=None,
        shift_hours=rng.choice((6, 8, 12)), efficiency=rng.choice((0.5, 1.0, 2.0)),
        allow_normal="no" if day % 4 == 2 else "yes",
    ) for day in range(5)]
    personal = [day_row(1, efficiency=0.75)] if seed % 2 else []
    for _ in range(8):
        groups = []
        for _resource in range(3):
            pairs = []
            for _segment in range(rng.randrange(8, 30)):
                start = rng.randrange(-8, 150) / 4
                pairs.append((start, start + rng.choice((-0.25, 0, 0.25, 0.5, 1, 2, 4))))
            groups.append(spans(*sorted(pairs)))
        case = slot_case(
            hours=rng.choice((0, 0.125, 0.5, 3, 12, 24)),
            machine=groups[0], operator=groups[1], downtime=groups[2],
            priority=rng.choice(("normal", "urgent", "critical")),
            prev_end=at(rng.choice((0, 0.25, 2, 6))),
            end_dt_exclusive=at(rng.choice((8, 32, 56, 80))),
            abort_after=at(4) if seed % 6 == 0 else None,
        )
        equivalent_slot(case, rows=rows, operator_rows=personal)


@pytest.mark.parametrize("seed", range(8))
def test_seeded_night_shifts_and_overlapping_policies(seed):
    rng = random.Random(919000 + seed)
    rows = [
        day_row(shift_start="22:00", shift_end="06:00"),
        day_row(1, shift_start="00:00" if seed % 2 else "04:00", shift_end="12:00", efficiency=0.5),
        day_row(2, shift_start="20:00", shift_end="06:00", efficiency=2.0),
    ]
    for _ in range(8):
        groups = []
        for _resource in range(3):
            pairs = []
            for _segment in range(20):
                start = rng.randrange(52, 220) / 4
                pairs.append((start, start + rng.choice((0, 0.25, 1, 3, 6))))
            groups.append(spans(*sorted(pairs)))
        equivalent_slot(slot_case(
            hours=rng.choice((0, 0.125, 2, 12, 30)), base_time=at(rng.choice((14, 15.75, 17, 20))),
            machine=groups[0], operator=groups[1], downtime=groups[2], end_dt_exclusive=at(32),
        ), rows=rows)


@pytest.mark.parametrize("hours", [0.25, 6.0, 30.0])
def test_next_day_efficiency_and_long_hours_recomputed_at_final_start(hours):
    case = slot_case(
        hours=hours, machine=spans((0, 2), (2, 4), (4, 8)),
        operator=spans((23, 24), (24, 25)), downtime=spans((25, 26)),
    )
    result, _, _ = equivalent_slot(case, rows=[
        day_row(1, shift_start="07:00", shift_end="15:00", efficiency=0.5),
        day_row(2, shift_start="06:00", shift_end="14:00", efficiency=2.0),
    ])
    assert result.start_time >= at(26)
    if hours == 0.25:
        assert result.start_time == at(26)
        assert result.total_hours == 0.5


def _schedule_input(end_date):
    operations, batches = [], {}
    for index in range(6):
        item = slot_case(hours=0.25 + index / 4, priority=("normal", "urgent", "critical")[index % 3])
        op, batch = item["op"], item["batch"]
        op.id, op.op_code, op.batch_id = index + 1, "OP" + str(index), "B" + str(index)
        batch.batch_id, batch.due_date = op.batch_id, BASE.date()
        operations.append(op)
        batches[batch.batch_id] = batch
    seeds = [ScheduleResult(
        op_id=1000 + index, op_code="SEED" + str(index), batch_id="SEED", seq=index,
        machine_id="M1", operator_id="O2", start_time=at(index / 30),
        end_time=at((index + 1) / 30), source="internal", op_type_name="MILL",
    ) for index in range(90)]
    return dict(
        operations=operations, batches=batches, start_dt=BASE, end_date=end_date,
        dispatch_mode="sgs", dispatch_rule="slack", seed_results=seeds,
        machine_downtimes={"M1": spans((3, 3.5), (3.5, 4))},
    )


@pytest.mark.parametrize("end_date", [None, "2026-09-08"])
def test_native_public_schedule_results_and_boundary_projection_match(end_date):
    source = _schedule_input(end_date)
    snapshots, counts = [], []
    for legacy in (True, False):
        args = deepcopy(source)
        with native_calendar([day_row(1, efficiency=0.5)]) as calendar:
            scheduler = GreedyScheduler(calendar_service=calendar)
            with counted_attempts(legacy) as attempts:
                results, summary, strategy, params = scheduler.schedule(**args)
            assert summary.scheduled_ops == (96 if end_date is None else 94)
            assert summary.failed_ops == (0 if end_date is None else 2)
            # duration_seconds is wall-clock telemetry, not a scheduling result.
            summary_fields = vars(summary).copy()
            assert summary_fields.pop("duration_seconds") >= 0
            snapshots.append((results, summary_fields, strategy, params))
            counts.append(attempts.call_count)
        assert args == source
    assert snapshots[0] == snapshots[1]
    assert counts[1] < counts[0]
