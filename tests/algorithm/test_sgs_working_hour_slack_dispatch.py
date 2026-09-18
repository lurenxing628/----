"""SGS dispatch keys read slack in working hours from the calendar, so a weekend no longer inflates slack.

Friday 08:00. A (6 h, due Monday) can run on M1 at once and finishes Friday 14:00: 82 wall-clock hours
but only 10 working hours before its due date expires. B (4 h, due Tuesday) waits for M2, which is down
until Monday, and finishes Monday 12:00: 36 wall-clock hours but 12 working hours of slack. Working-hour
slack picks A first; wall-clock slack picks B first. A calendar without work windows keeps the continuous
protocol, which the second test pins down. Pick order is read from the result list, which SGS appends in
dispatch order. Working hours are counted only up to the run's planning horizon (or a year past
the estimate without one); a far due date such as 2099-12-31 continues in wall-clock hours, so the
calendar never walks towards it and a due date past the century guard is still a legal input.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.greedy.dispatch.sgs_due_span import FAR_DUE_LOOKAHEAD, due_span_inputs, working_hour_span
from core.services.scheduler.calendar_working_hours import WorkingHoursPrefix
from core.services.scheduler.run.optimizer_proof_oracle import _default_config

START = datetime(2026, 1, 9, 8, 0)  # Friday
MONDAY_08 = datetime(2026, 1, 12, 8, 0)
FRIDAY_14 = START + timedelta(hours=6)


class _WeekdayCalendar:
    """08:00-16:00 Monday to Friday; the continuous stub below inherits everything but the working-hour span."""

    def _window(self, day):
        if day.weekday() >= 5:
            return None
        start = datetime.combine(day, datetime.min.time()) + timedelta(hours=8)
        return start, start + timedelta(hours=8)

    def adjust_to_working_time(self, dt, priority=None, machine_id=None, operator_id=None):
        cur = dt
        for _ in range(30):
            window = self._window(cur.date())
            if window is not None and cur < window[1]:
                return max(cur, window[0])
            cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time())
        raise RuntimeError("calendar walk exceeded 30 days")

    def add_working_hours(self, start, hours, priority=None, machine_id=None, operator_id=None):
        cur = self.adjust_to_working_time(start)
        remaining = float(hours)
        while remaining > 0:
            window = self._window(cur.date())
            assert window is not None, "adjust_to_working_time lands inside a work window"
            window_end = window[1]
            available = (window_end - cur).total_seconds() / 3600.0
            if remaining <= available + 1e-9:
                return cur + timedelta(hours=remaining)
            remaining -= available
            cur = self.adjust_to_working_time(window_end)
        return cur

    def get_efficiency(self, dt, machine_id=None, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt, days, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days))

    def working_hours_between(self, start, end, priority=None, machine_id=None, operator_id=None):
        sign, lo, hi = 1.0, start, end
        if hi < lo:
            sign, lo, hi = -1.0, end, start
        total, day = 0.0, lo.date()
        while day <= hi.date():
            window = self._window(day)
            if window is not None:
                clip_lo, clip_hi = max(window[0], lo), min(window[1], hi)
                if clip_hi > clip_lo:
                    total += (clip_hi - clip_lo).total_seconds() / 3600.0
            day += timedelta(days=1)
        return sign * total


class _WeekdayCalendarWithoutSpan(_WeekdayCalendar):
    working_hours_between = None  # type: ignore[assignment]


class _WalkRecordingCalendar(_WeekdayCalendar):
    """Answers through the production prefix (century guard included) and records every day it resolved."""

    def __init__(self):
        self.days_resolved = set()
        self.prefix = WorkingHoursPrefix(self._resolve)

    def _resolve(self, day):
        self.days_resolved.add(day)
        return self._window(day)

    def working_hours_between(self, start, end, priority=None, machine_id=None, operator_id=None):
        return self.prefix.between(start, end)


def _case():
    batches = {
        "A": SimpleNamespace(batch_id="A", priority="normal", due_date="2026-01-12", quantity=1.0),
        "B": SimpleNamespace(batch_id="B", priority="normal", due_date="2026-01-13", quantity=1.0),
    }
    operations = [
        SimpleNamespace(id=1, op_code="A1", batch_id="A", seq=1, source="internal", machine_id="M1", operator_id="O1",
                        setup_hours=6.0, unit_hours=0.0, op_type_id="", op_type_name="cut"),
        SimpleNamespace(id=2, op_code="B1", batch_id="B", seq=1, source="internal", machine_id="M2", operator_id="O2",
                        setup_hours=4.0, unit_hours=0.0, op_type_id="", op_type_name="cut"),
    ]
    return operations, batches


def _pick_order(calendar, rule):
    operations, batches = _case()
    scheduler = GreedyScheduler(calendar_service=calendar, config_service=_default_config())
    results, summary, _strategy, _params = scheduler.schedule(
        operations=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, start_dt=START,
        machine_downtimes={"M2": [(START, MONDAY_08)]}, dispatch_mode="sgs", dispatch_rule=rule,
        seed_results=[], strict_mode=True,
    )
    assert summary.failed_ops == 0
    by_id = {row.op_id: row for row in results}
    assert (by_id[1].start_time, by_id[1].end_time) == (START, START + timedelta(hours=6))
    assert (by_id[2].start_time, by_id[2].end_time) == (MONDAY_08, MONDAY_08 + timedelta(hours=4))
    return [row.op_id for row in results]


@pytest.mark.parametrize("rule", ["slack", "cr"])
def test_working_hour_slack_dispatches_the_batch_that_is_tight_before_the_weekend_first(rule):
    assert _pick_order(_WeekdayCalendar(), rule) == [1, 2]


@pytest.mark.parametrize("rule", ["slack", "cr"])
def test_a_calendar_without_work_windows_keeps_the_wall_clock_order(rule):
    assert _pick_order(_WeekdayCalendarWithoutSpan(), rule) == [2, 1]


def test_due_span_inputs_use_the_calendar_and_keep_the_no_due_sentinel_continuous():
    calendar = _WeekdayCalendar()
    slack, time_left = due_span_inputs(calendar, due_date=datetime(2026, 1, 12).date(), est_start=START, est_end=FRIDAY_14,
                                       priority="normal", operator_id="", horizon=None)
    assert (slack, time_left) == (10.0, 16.0)
    slack, time_left = due_span_inputs(calendar, due_date=None, est_start=START, est_end=FRIDAY_14, priority="normal",
                                       operator_id="", horizon=None)
    assert slack > 1e6 and time_left == slack + 6.0
    assert working_hour_span(_WeekdayCalendarWithoutSpan(), START, FRIDAY_14, priority=None, operator_id="",
                             horizon=MONDAY_08) == 6.0


def test_far_due_dates_count_working_hours_up_to_the_horizon_and_never_walk_past_it():
    calendar = _WalkRecordingCalendar()
    horizon = datetime(2026, 2, 1)  # the run's exclusive planning end
    spans = {}
    for due in (date(2026, 1, 20), date(2099, 12, 31), date(2150, 1, 1)):  # the last one is past the century guard
        spans[due] = due_span_inputs(calendar, due_date=due, est_start=START, est_end=FRIDAY_14, priority="normal",
                                     operator_id="", horizon=horizon)
    slack_near, slack_far, slack_farther = (spans[due][0] for due in sorted(spans))
    assert slack_near < slack_far < slack_farther
    assert max(calendar.days_resolved) <= horizon.date()
    # Working hours to the horizon, then wall-clock hours from the horizon to the due instant.
    far = due_exclusive(date(2099, 12, 31))
    assert slack_far == calendar.prefix.between(FRIDAY_14, horizon) + (far - horizon).total_seconds() / 3600.0
    assert spans[date(2099, 12, 31)][1] == slack_far + 6.0
    # A due date inside the horizon is pure working hours, as before.
    assert slack_near == calendar.prefix.between(FRIDAY_14, due_exclusive(date(2026, 1, 20)))


def test_without_a_planning_end_the_working_hour_part_looks_a_year_past_the_estimate():
    calendar = _WalkRecordingCalendar()
    slack, time_left = due_span_inputs(calendar, due_date=date(2099, 12, 31), est_start=START, est_end=FRIDAY_14,
                                       priority="normal", operator_id="", horizon=None)
    assert time_left == slack + 6.0
    assert max(calendar.days_resolved) == (START + FAR_DUE_LOOKAHEAD).date()


def test_an_estimate_past_the_horizon_is_measured_in_wall_clock_hours_only():
    calendar = _WalkRecordingCalendar()
    horizon = datetime(2026, 1, 12)
    late_start = datetime(2026, 1, 20, 8, 0)
    slack, time_left = due_span_inputs(calendar, due_date=date(2026, 1, 30), est_start=late_start,
                                       est_end=late_start + timedelta(hours=6), priority="normal", operator_id="", horizon=horizon)
    assert time_left == (due_exclusive(date(2026, 1, 30)) - late_start).total_seconds() / 3600.0
    assert slack == time_left - 6.0
    assert calendar.days_resolved == set(), "nothing lies before the horizon, so the calendar is never asked"
