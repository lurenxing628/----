"""跨午夜重叠班段只计算一次，当前班段优先。"""

from datetime import datetime
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


@pytest.mark.parametrize('priority', ["normal"])
@pytest.mark.parametrize('efficiency', [1])
def test_overlap_is_counted_once_and_calendar_hours_are_not_efficiency_weighted(priority, efficiency):
    cal = engine(efficiency=efficiency)
    start = dt('06T04:00')
    assert cal.working_hours_between(start, dt('06T06:00'), priority) == 2
    for hours in (.25, 2, 9, 15):
        end = cal.add_working_hours(start, hours, priority)
        assert cal.working_hours_between(start, end, priority) == pytest.approx(hours)
        assert cal.working_hours_between(end, start, priority) == pytest.approx(-hours)


def test_current_window_priority_wins_and_tail_resumes_after_short_current_window():
    cal = engine(today_normal='no', start='05:00', end='05:30')
    assert cal.add_working_hours(dt('06T04:00'), 1.5, 'normal') == dt('06T06:00')
    assert cal.adjust_to_working_time(dt('06T05:00'), 'normal') == dt('06T05:30')
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'normal') == 1.5
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'urgent') == 2
