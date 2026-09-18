"""SGS dispatch keys read slack in working hours from the calendar, so a weekend no longer inflates slack.

Friday 08:00. A (6 h, due Monday) can run on M1 at once and finishes Friday 14:00: 82 wall-clock hours
but only 10 working hours before its due date expires. B (4 h, due Tuesday) waits for M2, which is down
until Monday, and finishes Monday 12:00: 36 wall-clock hours but 12 working hours of slack. Working-hour
slack picks A first; wall-clock slack picks B first. A calendar without work windows keeps the continuous
protocol, which the second test pins down. Pick order is read from the result list, which SGS appends in
dispatch order.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.greedy.dispatch.sgs_due_span import due_span_inputs, working_hour_span
from core.services.scheduler.run.optimizer_proof_oracle import _default_config

START = datetime(2026, 1, 9, 8, 0)  # Friday
MONDAY_08 = datetime(2026, 1, 12, 8, 0)


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
            window_end = self._window(cur.date())[1]
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
    friday_14 = START + timedelta(hours=6)
    slack, time_left = due_span_inputs(calendar, due_date=datetime(2026, 1, 12).date(), est_start=START, est_end=friday_14,
                                       priority="normal", operator_id="")
    assert (slack, time_left) == (10.0, 16.0)
    slack, time_left = due_span_inputs(calendar, due_date=None, est_start=START, est_end=friday_14, priority="normal", operator_id="")
    assert slack > 1e6 and time_left == slack + 6.0
    assert working_hour_span(_WeekdayCalendarWithoutSpan(), START, friday_14, priority=None, operator_id="") == 6.0
