"""Legacy boundaries, extension refusal and errors must survive busy-block skipping."""

from datetime import timedelta
from types import MethodType
from unittest.mock import patch

import pytest

from core.algorithm_runtime.downtime import SegmentOverlapIndex, find_overlap_shift_end
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    ExecutionResourceReservation,
)
from tests._support.busy_block_case import (
    at,
    day_row,
    equivalent_slot,
    native_calendar,
    run_estimate,
    slot_case,
    spans,
)


def test_covered_end_does_not_change_original_single_hop_shift_end():
    segments = spans((0, 1), (1, 2), (2, 3), (3.5, 4))
    index = SegmentOverlapIndex(segments)
    queries = [(0, 0.25, 1), (1, 1.25, 2), (2, 2.25, 3), (3, 3.5, None),
               (1, 1, None), (1.5, 1.5, 2), (1.75, 1.25, 2)]
    for warm_coverage in (False, True):
        if warm_coverage:
            assert index.covered_end(at(1)) == at(3)
        for start, end, expected in queries:
            expected = None if expected is None else at(expected)
            assert index.shift_end(at(start), at(end)) == expected
            assert find_overlap_shift_end(segments, at(start), at(end)) == expected


@pytest.mark.parametrize("hours,efficiency", [(0, 1), (1e-12, 1), (1e-10, 1), (1, 1e12)])
def test_zero_or_submicrosecond_duration_keeps_touching_boundary(hours, efficiency):
    result, old_count, new_count = equivalent_slot(slot_case(
        hours=hours, base_time=at(0.5), machine=spans((0, 1), (1, 2)),
    ), rows=[day_row(efficiency=efficiency)])
    assert result.start_time == result.end_time == at(1)
    assert old_count == new_count == 2


def test_one_microsecond_positive_interval_still_uses_busy_skip():
    result, old_count, new_count = equivalent_slot(slot_case(
        hours=1 / 3600000000, base_time=at(0.5), machine=spans((0, 1), (1, 2)),
    ))
    assert result.start_time == at(2)
    assert result.end_time == at(2) + timedelta(microseconds=1)
    assert (old_count, new_count) == (3, 2)


@pytest.mark.parametrize("gap_microseconds", [29, 30, 31])
def test_native_microsecond_gap_is_never_rounded_into_busy_coverage(gap_microseconds):
    second_start = at(1) + timedelta(microseconds=gap_microseconds)
    result, _, _ = equivalent_slot(slot_case(
        hours=30 / 3600000000, machine=[(at(), at(1)), (second_start, at(2)), (at(2), at(3))],
    ))
    expected_start = at(3) if gap_microseconds < 30 else at(1)
    assert result.start_time == expected_start
    assert result.end_time == expected_start + timedelta(microseconds=30)


@pytest.mark.parametrize("cutoff,expected_start,hit", [
    (-0.25, 0, True), (0, 1, True), (1, 2, True), (3, 3, False),
])
def test_abort_retains_first_strictly_greater_hop(cutoff, expected_start, hit):
    result, old_count, new_count = equivalent_slot(slot_case(
        machine=spans((0, 1), (1, 2), (2, 3)), abort_after=at(cutoff), end_dt_exclusive=at(1),
    ))
    assert result.start_time == at(expected_start)
    assert result.abort_after_hit is hit
    assert result.blocked_by_window is (not hit)
    assert old_count == new_count
    if hit:
        assert result.total_hours == 0
        assert result.end_time == result.start_time


@pytest.mark.parametrize("cutoff,blocked", [(3.25, True), (3.250001, False), (3, True)])
def test_exclusive_end_window_flag_includes_exact_end(cutoff, blocked):
    result, _, _ = equivalent_slot(slot_case(
        machine=spans((0, 1), (1, 2), (2, 3)), end_dt_exclusive=at(cutoff),
    ))
    assert result.blocked_by_window is blocked
    assert not result.abort_after_hit


@pytest.mark.parametrize("cutoff,hit", [(23, True), (24, False)])
def test_abort_compares_after_next_working_day_adjustment(cutoff, hit):
    result, old_count, new_count = equivalent_slot(slot_case(
        base_time=at(9), abort_after=at(cutoff),
    ))
    assert result.start_time == at(24)
    assert result.abort_after_hit is hit
    assert old_count == new_count == (0 if hit else 1)


@pytest.mark.parametrize("priority,expected", [("normal", 24), ("urgent", 3), ("critical", 3)])
def test_native_priority_restrictions_not_skipped(priority, expected):
    result, _, _ = equivalent_slot(slot_case(
        priority=priority, machine=spans((0, 1), (1, 2), (2, 3)),
    ), rows=[day_row(allow_normal="no")])
    assert result.start_time == at(expected)


def test_personal_calendar_reopens_global_holiday_with_own_efficiency():
    result, _, _ = equivalent_slot(
        slot_case(machine=spans((0, 1), (1, 2), (2, 3))),
        rows=[day_row(allow_normal="no", allow_urgent="no", shift_hours=0, shift_end=None)],
        operator_rows=[day_row(efficiency=0.5)],
    )
    assert result.start_time == at(3)
    assert result.end_time == at(3.5)
    assert result.total_hours == 0.5


@pytest.mark.parametrize("start,next_start,expected", [
    (14, "08:00", 18), (17, "08:00", 18), (17, "00:00", 18),
])
def test_night_shift_and_overlapping_next_day_policy(start, next_start, expected):
    rows = [day_row(shift_start="22:00", shift_end="06:00", efficiency=1.0),
            day_row(1, shift_start=next_start, shift_end="16:00", efficiency=2.0)]
    result, _, _ = equivalent_slot(slot_case(
        base_time=at(start), machine=spans((14, 15), (15, 16), (16, 17), (17, 18)),
    ), rows=rows)
    assert result.start_time == at(expected)
    assert result.total_hours == (0.125 if next_start == "00:00" else 0.25)


def test_native_certificate_stops_at_midnight_and_refuses_previous_day_ownership():
    rows = [day_row(shift_start="22:00", shift_end="06:00")]
    with native_calendar(rows) as calendar:
        assert calendar.certified_slot_window(at(14), operator_id="O1") == (at(14), at(16))
        assert calendar.certified_slot_window(at(17), operator_id="O1") is None


class CustomCalendar(CalendarService):
    def get_efficiency(self, dt, machine_id=None, operator_id=None):
        if at(1) <= dt < at(2):
            return 0.5
        return super().get_efficiency(dt, machine_id=machine_id, operator_id=operator_id)


def test_custom_calendar_disables_skip_even_when_it_inherits_certificate():
    with native_calendar(calendar_type=CustomCalendar) as calendar:
        assert calendar.certified_slot_window(at(), operator_id="O1") is None
    _, old_count, new_count = equivalent_slot(
        slot_case(machine=spans((0, 1), (1, 2), (2, 3))), calendar_type=CustomCalendar,
    )
    assert old_count == new_count == 4


class CustomEngine(CalendarEngine):
    def get_efficiency(self, dt, machine_id=None, operator_id=None):
        return super().get_efficiency(dt, machine_id=machine_id, operator_id=operator_id)


def test_native_service_with_custom_engine_retains_legacy_attempts():
    outputs = []
    for legacy in (True, False):
        with native_calendar() as calendar:
            calendar._engine = CustomEngine(calendar.conn)
            assert calendar.certified_slot_window(at(), operator_id="O1") is None
            outputs.append(run_estimate(calendar, slot_case(
                machine=spans((0, 1), (1, 2), (2, 3)),
            ), legacy=legacy))
    assert outputs[0] == outputs[1]
    assert outputs[0][1] == 4


def test_execution_getattr_overlay_does_not_borrow_native_certificate():
    outputs = []
    for legacy in (True, False):
        with native_calendar() as native:
            overlay = ExecutionResourceCalendar(native, [
                ExecutionResourceReservation(99, "M2", "O1", at(), at(0.5)),
            ])
            assert overlay.certified_slot_window(at(0.5), operator_id="O1") is not None
            outputs.append(run_estimate(overlay, slot_case(
                machine=spans((0.5, 1), (1, 2), (2, 3)),
            ), legacy=legacy))
            assert overlay._release_by_operator == {"O1": at(0.5)}
    assert outputs[0] == outputs[1]
    assert outputs[0][0].start_time == at(3)
    assert outputs[0][1] == 4


@pytest.mark.parametrize("target,name", [
    ("service", "get_efficiency"), ("service", "adjust_to_working_time"),
    ("engine", "get_efficiency"), ("engine", "adjust_to_working_time"),
    ("engine", "policy_for_datetime"), ("engine", "_policy_for_datetime"),
    ("engine", "_policy_for_date"),
])
@pytest.mark.parametrize("scope", ["instance", "class"])
def test_instrumented_native_methods_keep_all_legacy_calls(target, name, scope):
    outputs, traces = [], []
    for legacy in (True, False):
        with native_calendar() as calendar:
            subject = calendar if target == "service" else calendar._engine
            original = getattr(type(subject), name)
            calls = []

            def instrumented(self, *args, **kwargs):
                calls.append((args, kwargs))
                return original(self, *args, **kwargs)

            owner = subject if scope == "instance" else type(subject)
            replacement = MethodType(instrumented, subject) if scope == "instance" else instrumented
            with patch.object(owner, name, replacement):
                assert calendar.certified_slot_window(at(), operator_id="O1") is None
                calls.clear()
                outputs.append(run_estimate(calendar, slot_case(
                    machine=spans((0, 1), (1, 2), (2, 3)),
                ), legacy=legacy))
            traces.append(calls)
    assert outputs[0] == outputs[1]
    assert outputs[0][1] == 4
    assert traces[0] == traces[1]
    # The public engine wrapper is only used by certification, never by the old estimator.
    assert bool(traces[0]) is (name != "policy_for_datetime")


@pytest.mark.parametrize("invalid", [0, -1, "invalid", float("inf")])
def test_native_bad_efficiency_keeps_exception_type_field_and_message(invalid):
    errors = []
    for legacy in (True, False):
        with native_calendar([day_row(1, efficiency=invalid)]) as calendar:
            with pytest.raises(ValueError) as caught:
                run_estimate(calendar, slot_case(machine=spans((0, 4), (4, 8))), legacy=legacy)
            errors.append((type(caught.value), str(caught.value), getattr(caught.value, "field", None)))
    assert errors[0] == errors[1]
    assert "efficiency" in errors[0][1]


def test_unsorted_zero_hop_input_is_not_eagerly_validated_or_written():
    result, old_count, new_count = equivalent_slot(slot_case(machine=spans((3, 4), (0, 1))))
    assert result.start_time == at()
    assert old_count == new_count == 1


@pytest.mark.parametrize("resource", ["machine", "operator", "downtime"])
def test_unsorted_hopping_input_keeps_original_error(resource):
    errors = []
    for legacy in (True, False):
        with native_calendar() as calendar:
            with pytest.raises(ValueError) as caught:
                run_estimate(calendar, slot_case(**{resource: spans((0, 1), (3, 4), (2, 3))}), legacy=legacy)
            errors.append((type(caught.value), str(caught.value)))
    assert errors[0] == errors[1]


def test_custom_fallback_and_error_at_intermediate_hop_remain_visible():
    for fail in (False, True):
        outputs, traces = [], []
        for legacy in (True, False):
            with native_calendar() as calendar:
                original = calendar.get_efficiency
                calls = []

                def efficiency(dt, **kwargs):
                    calls.append(dt)
                    if dt == at(1):
                        if fail:
                            raise RuntimeError("intermediate-efficiency-error")
                        return None
                    return original(dt, **kwargs)

                with patch.object(calendar, "get_efficiency", side_effect=efficiency):
                    case = slot_case(machine=spans((0, 1), (1, 2), (2, 3)))
                    if fail:
                        with pytest.raises(RuntimeError, match="intermediate-efficiency-error") as caught:
                            run_estimate(calendar, case, legacy=legacy)
                        outputs.append((type(caught.value), str(caught.value)))
                    else:
                        result, count = run_estimate(calendar, case, legacy=legacy)
                        assert result.efficiency_fallback_used
                        outputs.append((result, count))
                traces.append(calls)
        assert outputs[0] == outputs[1]
        assert traces[0] == traces[1]
        assert at(1) in traces[0]
