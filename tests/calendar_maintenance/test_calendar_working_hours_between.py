"""CalendarEngine.working_hours_between: signed allowed working hours, same DayPolicy scope as add_working_hours.

The prefix cache must match a naive per-day clipping walk on arbitrary spans (night shifts, priority-blocked
days), invalidate with the policy cache, be memoized per decode, and be exposed by every production calendar.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar, native_timing_calendar
from core.infrastructure.errors import ValidationError
from core.services.scheduler.calendar_engine import NATIVE_TIMING_METHODS, CalendarEngine
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.calendar_working_hours import MAX_SPAN_DAYS
from core.services.scheduler.run.optimizer_proof_oracle import _ContinuousCalendar
from core.services.scheduler.run.schedule_execution_reservations import ExecutionResourceCalendar

FRI_16 = datetime(2026, 1, 9, 16, 0)   # Friday
TUE_00 = datetime(2026, 1, 13, 0, 0)   # exclusive due instant of Monday 2026-01-12


def _default_engine() -> CalendarEngine:
    engine = CalendarEngine(conn=None)
    engine._resolve_calendar_row = lambda date_str, _op_id: engine._default_for_date(date_str)  # type: ignore[method-assign]
    return engine


def _row(date_str, *, shift_start="08:00", shift_end="16:00", allow_normal="yes", allow_urgent="yes", shift_hours=8.0):
    return SimpleNamespace(date=date_str, day_type="workday", shift_start=shift_start, shift_end=shift_end,
                           shift_hours=shift_hours, efficiency=1.0, allow_normal=allow_normal, allow_urgent=allow_urgent)


def _off_row(date_str):
    # No shift_end: shift_end == shift_start would mean a 24 h shift, so rest days carry only shift_hours=0.
    return _row(date_str, shift_hours=0.0, shift_end=None, allow_normal="no", allow_urgent="no")


def _mixed_engine() -> CalendarEngine:
    """Wednesdays run a 20:00-04:00 night shift, Thursdays refuse normal batches, weekends are off."""
    engine = CalendarEngine(conn=None)

    def resolve(date_str, _op_id):
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
        if day.weekday() >= 5:
            return _off_row(date_str)
        if day.weekday() == 2:
            return _row(date_str, shift_start="20:00", shift_end="04:00")
        if day.weekday() == 3:
            return _row(date_str, allow_normal="no")
        return _row(date_str)

    engine._resolve_calendar_row = resolve  # type: ignore[method-assign]
    return engine


def _naive(engine: CalendarEngine, start: datetime, end: datetime, priority=None) -> float:
    sign, lo, hi = 1.0, start, end
    if hi < lo:
        sign, lo, hi = -1.0, end, start
    total = 0.0
    day = lo.date() - timedelta(days=1)
    while day <= hi.date():
        policy = engine._policy_for_date(day.isoformat(), operator_id=None)
        if policy.is_priority_allowed(priority) and policy.shift_hours > 0:
            window_start, window_end = policy.work_window()
            clip_lo, clip_hi = max(window_start, lo), min(window_end, hi)
            if clip_hi > clip_lo:
                total += (clip_hi - clip_lo).total_seconds() / 3600.0
        day += timedelta(days=1)
    return sign * total


def test_weekend_gap_counts_only_working_hours_and_is_signed():
    engine = _default_engine()
    assert engine.working_hours_between(FRI_16, TUE_00) == 8.0          # only Monday's shift
    assert engine.working_hours_between(datetime(2026, 1, 12, 12), datetime(2026, 1, 14)) == 12.0
    assert engine.working_hours_between(TUE_00, FRI_16) == -8.0
    assert engine.working_hours_between(FRI_16, FRI_16) == 0.0
    assert engine.working_hours_between(datetime(2026, 1, 10), datetime(2026, 1, 12)) == 0.0
    assert engine.working_hours_between(datetime(2026, 1, 12, 9), datetime(2026, 1, 12, 11, 30)) == 2.5
    assert engine.working_hours_between(datetime(2026, 1, 12, 8), datetime(2026, 1, 19, 8)) == 40.0
    assert engine.working_hours_between(datetime(2026, 1, 12, 6), datetime(2026, 1, 12, 20)) == 8.0


@pytest.mark.parametrize("priority", [None, "normal", "urgent", "critical", "Urgent"])
def test_prefix_matches_naive_clipping_on_random_spans_with_night_shift_and_blocked_days(priority):
    engine = _mixed_engine()
    rng = random.Random(20260918)
    base = datetime(2026, 1, 5)
    for _ in range(300):
        start = base + timedelta(minutes=rng.randint(-20000, 60000))
        end = base + timedelta(minutes=rng.randint(-20000, 60000))
        assert engine.working_hours_between(start, end, priority=priority) == pytest.approx(_naive(engine, start, end, priority))


def test_night_shift_hours_after_midnight_belong_to_the_shift_start_day():
    engine = _mixed_engine()
    wednesday_22 = datetime(2026, 1, 7, 22, 0)
    thursday_03 = datetime(2026, 1, 8, 3, 0)
    assert engine.working_hours_between(wednesday_22, thursday_03) == 5.0
    # Thursday refuses normal batches but accepts urgent ones; the night shift tail still counts for both.
    assert engine.working_hours_between(wednesday_22, datetime(2026, 1, 8, 20), priority="normal") == 6.0
    assert engine.working_hours_between(wednesday_22, datetime(2026, 1, 8, 20), priority="urgent") == 14.0


def test_prefix_cache_is_cleared_with_the_policy_cache():
    engine = _default_engine()
    assert engine.working_hours_between(FRI_16, TUE_00) == 8.0
    engine._resolve_calendar_row = lambda date_str, _op_id: _off_row(date_str)  # type: ignore[method-assign]
    assert engine.working_hours_between(FRI_16, TUE_00) == 8.0   # still served from the prefix
    engine.clear_policy_cache()
    assert engine.working_hours_between(FRI_16, TUE_00) == 0.0


def test_span_magnitude_is_bounded_like_calendar_days():
    engine = _default_engine()
    with pytest.raises(ValidationError):
        engine.working_hours_between(FRI_16, FRI_16 + timedelta(days=MAX_SPAN_DAYS + 1))
    with pytest.raises(ValidationError):
        engine.working_hours_between("2026-01-09", FRI_16)  # type: ignore[arg-type]


def test_memo_answers_repeats_and_an_override_breaks_the_native_certificate():
    engine = _default_engine()
    memo = MemoizedTimingCalendar(engine)
    first = memo.working_hours_between(FRI_16, TUE_00, priority=None, operator_id=None)
    assert first == 8.0
    assert memo.working_hours_between(FRI_16, TUE_00, priority=None, operator_id=None) == 8.0
    assert (memo.hits, memo.misses) == (1, 1)
    assert "working_hours_between" in NATIVE_TIMING_METHODS
    assert native_timing_calendar(engine)

    class Instrumented(CalendarEngine):
        def working_hours_between(self, start, end, priority=None, machine_id=None, operator_id=None):
            return 0.0

    assert not native_timing_calendar(Instrumented(conn=None))


def test_every_production_calendar_exposes_the_working_hour_span():
    engine = _default_engine()
    assert CalendarService.working_hours_between is not None
    assert _ContinuousCalendar().working_hours_between(FRI_16, TUE_00, priority=None, operator_id=None) == 80.0
    wrapped = ExecutionResourceCalendar(engine, [])
    assert wrapped.working_hours_between(FRI_16, TUE_00, priority=None, operator_id=None) == 8.0
