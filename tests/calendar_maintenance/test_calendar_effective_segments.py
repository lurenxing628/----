"""Overlapping night shifts use one owner; advancement and signed hours agree."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.services.scheduler.calendar.engine import CalendarEngine


def dt(text):
    return datetime.fromisoformat('2026-10-' + text)


def engine(today_normal='yes', previous_normal='yes', *, start='05:00', end='13:00', efficiency=1):
    result = CalendarEngine(None)

    def resolve(day, _):
        night = day == '2026-10-05'
        return SimpleNamespace(date=day, day_type='workday', shift_hours=8, shift_start='22:00' if night else start,
                               shift_end='06:00' if night else end, efficiency=efficiency,
                               allow_normal=previous_normal if night else today_normal, allow_urgent='yes')
    result._resolve_calendar_row = resolve
    return result


@pytest.mark.parametrize('priority', ['normal', 'urgent', 'critical'])
@pytest.mark.parametrize('efficiency', [.5, 1, 2])
def test_overlap_is_counted_once_and_calendar_hours_are_not_efficiency_weighted(priority, efficiency):
    cal = engine(efficiency=efficiency)
    start = dt('06T04:00')
    assert cal.working_hours_between(start, dt('06T06:00'), priority) == 2
    for hours in (.25, 2, 9, 15):
        end = cal.add_working_hours(start, hours, priority)
        assert cal.working_hours_between(start, end, priority) == pytest.approx(hours)
        assert cal.working_hours_between(end, start, priority) == pytest.approx(-hours)


def test_disallowed_previous_tail_does_not_skip_current_day_shift():
    cal = engine(previous_normal='no', start='08:00', end='16:00')
    assert cal.adjust_to_working_time(dt('06T00:00'), 'normal') == dt('06T08:00')
    assert cal.add_working_hours(dt('06T00:00'), 2, 'normal') == dt('06T10:00')


def test_current_window_priority_wins_and_tail_resumes_after_short_current_window():
    cal = engine(today_normal='no', start='05:00', end='05:30')
    assert cal.add_working_hours(dt('06T04:00'), 1.5, 'normal') == dt('06T06:00')
    assert cal.adjust_to_working_time(dt('06T05:00'), 'normal') == dt('06T05:30')
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'normal') == 1.5
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'urgent') == 2


def test_current_forbidden_window_is_never_crossed_by_previous_allowed_tail():
    cal = engine(today_normal='no')
    # Two days that accept normal work keep the calculation finite after the blocked day.
    original = cal._resolve_calendar_row
    def resolve(day, op):
        row = original(day, op)
        if day > '2026-10-06':
            row.allow_normal = 'yes'
        return row
    cal._resolve_calendar_row = resolve
    start = dt('06T04:00')
    assert cal.add_working_hours(start, 2, 'normal') == dt('07T06:00')
    assert cal.working_hours_between(start, dt('06T13:00'), 'normal') == 1


def test_touching_and_24h_windows_and_cache_invalidation():
    cal = engine(start='06:00', end='06:00')
    assert cal.working_hours_between(dt('06T00:00'), dt('07T00:00')) == 24
    assert cal.add_working_hours(dt('06T00:00'), 24) == dt('07T00:00')
    cal._resolve_calendar_row = lambda day, _: SimpleNamespace(date=day, day_type='holiday', shift_hours=0,
        shift_start='00:00', shift_end=None, efficiency=1, allow_normal='no', allow_urgent='no')
    cal.clear_policy_cache()
    assert cal.working_hours_between(dt('06T00:00'), dt('06T00:00') + timedelta(days=2)) == 0


def test_last_representable_day_still_supports_same_day_work():
    cal = CalendarEngine(None)
    cal._resolve_calendar_row = lambda day, _: cal._default_for_date(day)
    start, end = datetime(9999, 12, 31, 8, 30), datetime(9999, 12, 31, 9, 30)
    assert cal.adjust_to_working_time(start) == start
    assert cal.add_working_hours(start, 1) == end
    assert cal.working_hours_between(start, end) == 1
