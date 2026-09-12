"""Cross-resource occupancy closure preserves exact free gaps and native boundaries."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from core.algorithm_runtime.busy_block_skip import advance_busy_block
from core.algorithm_runtime.downtime import SegmentOverlapIndex
from tests._support.busy_block_case import at, day_row, equivalent_slot, native_calendar, slot_case, spans


@pytest.mark.parametrize("group_count", [2, 3])
def test_interleaved_occupancy_is_solved_without_reestimating_each_resource_hop(group_count):
    segments = spans(*[(i / 12, (i + 1) / 12) for i in range(72)])
    groups = [segments[index::group_count] for index in range(group_count)]
    groups.extend([[]] * (3 - group_count))
    result, legacy_attempts, attempts = equivalent_slot(slot_case(
        hours=0.01, machine=groups[0], operator=groups[1], downtime=groups[2],
    ))
    assert result.start_time == at(6)
    assert result.end_time == at(6) + timedelta(seconds=36)
    assert legacy_attempts == 73
    assert attempts == 2


@pytest.mark.parametrize("gap_us", [1, 29, 30, 31])
def test_union_never_closes_a_real_microsecond_gap(gap_us):
    result, _, _ = equivalent_slot(slot_case(
        hours=gap_us / 3600000000, base_time=at(0.5),
        machine=spans((0, 1), (2, 3)),
        operator=[(at(1) + timedelta(microseconds=gap_us), at(2))],
    ))
    assert result.start_time == at(1)
    assert result.end_time == at(1) + timedelta(microseconds=gap_us)


def test_union_does_not_skip_next_day_efficiency_or_calendar_ownership():
    result, _, _ = equivalent_slot(slot_case(
        hours=1, machine=spans((0, 2), (4, 6), (24, 25)),
        operator=spans((2, 4), (6, 8)), downtime=spans((25, 26)),
    ), rows=[day_row(1, efficiency=0.5)])
    assert result.start_time == at(26)
    assert result.end_time == at(28)
    assert result.total_hours == 2


class _TupleSubclass(tuple):
    pass


class _DateSubclass(datetime):
    pass


@pytest.mark.parametrize("segments", [
    [[at(), at(1)]],
    [_TupleSubclass((at(), at(1)))],
    [(at(), _DateSubclass.fromtimestamp(at(1).timestamp()))],
    _TupleSubclass(((at(), at(1)),)),
])
def test_extended_segment_inputs_keep_single_group_behavior(segments):
    index = SegmentOverlapIndex(segments)
    index.covered_end(at())
    assert index.has_native_coverage() is False


def test_native_append_derives_pure_coverage_without_modifying_old_index():
    old = SegmentOverlapIndex(((at(), at(1)),))
    assert old.covered_end(at()) == at(1)
    assert old.has_native_coverage()
    new = old.with_appended_segment(((at(), at(1)), (at(1), at(2))))
    assert new is not None and new.has_native_coverage()
    assert old.covered_end(at(1)) is None
    assert new.covered_end(at(1)) == at(2)


def test_instrumented_index_method_keeps_original_single_query_per_group():
    indexes = [SegmentOverlapIndex(spans((0, 1), (2, 3))),
               SegmentOverlapIndex(spans((1, 2), (3, 4))), SegmentOverlapIndex(())]
    original = SegmentOverlapIndex.covered_end
    calls = []

    def wrapped(index, instant):
        calls.append((index, instant))
        return original(index, instant)

    with native_calendar() as calendar, patch.object(SegmentOverlapIndex, "covered_end", wrapped):
        result = advance_busy_block(calendar, earliest=at(), shift_to=at(1), segment_groups=indexes,
            total_base=0.01, priority="normal", operator_id="O1", abort_after=None)
    assert result == at(2)
    assert calls == [(index, at(1)) for index in indexes]
