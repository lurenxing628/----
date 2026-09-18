"""Working hours between two instants on a day-policy calendar.

Dispatch rules compare a batch's remaining time against processing hours, so both must be
working hours. The calendar answers "how many allowed working hours lie between ``start``
and ``end``" through a per-(operator, priority) prefix of daily window hours: after the
first walk over a span, later spans over the same days cost two dictionary lookups.

The result is signed: ``end`` before ``start`` gives the negated span. A day's window may
run into the next calendar day (night shift) but never beyond it, matching the one-day
look-back of ``CalendarEngine._policy_for_datetime``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

Window = Optional[Tuple[datetime, datetime]]
WindowResolver = Callable[[date], Window]
# Same magnitude bound as add_calendar_days: spans beyond a century are input errors, not schedules.
MAX_SPAN_DAYS = 36500


def clip_window_hours(window: Window, limit: datetime) -> float:
    """Hours of ``window`` that lie strictly before ``limit``."""
    if window is None:
        return 0.0
    start, end = window
    end = min(end, limit)
    if end <= start:
        return 0.0
    return (end - start).total_seconds() / 3600.0


class WorkingHoursPrefix:
    """Cumulative allowed window hours by date for one (operator, priority) pair.

    ``cumulative(day)`` is the signed sum of full window hours of all days in
    ``[anchor, day)`` where ``anchor`` is the first day ever requested; only
    differences of two cumulative values are ever used, so the anchor cancels.
    """

    __slots__ = ("_resolve", "_anchor", "_forward", "_backward", "_windows")

    def __init__(self, resolve: WindowResolver) -> None:
        self._resolve = resolve
        self._anchor: Optional[date] = None
        # _forward[i] = hours of days anchor .. anchor+i-1; _backward[i] = hours of days anchor-i .. anchor-1.
        self._forward: List[float] = [0.0]
        self._backward: List[float] = [0.0]
        self._windows: Dict[date, Window] = {}

    def window(self, day: date) -> Window:
        found = self._windows.get(day)
        if found is None and day not in self._windows:
            found = self._resolve(day)
            self._windows[day] = found
        return found

    def _hours(self, day: date) -> float:
        window = self.window(day)
        if window is None:
            return 0.0
        return (window[1] - window[0]).total_seconds() / 3600.0

    def cumulative(self, day: date) -> float:
        if self._anchor is None:
            self._anchor = day
        offset = (day - self._anchor).days
        if offset >= 0:
            while len(self._forward) <= offset:
                index = len(self._forward) - 1
                self._forward.append(self._forward[-1] + self._hours(self._anchor + timedelta(days=index)))
            return self._forward[offset]
        distance = -offset
        while len(self._backward) <= distance:
            index = len(self._backward)
            self._backward.append(self._backward[-1] + self._hours(self._anchor - timedelta(days=index)))
        return -self._backward[distance]

    def hours_until(self, instant: datetime) -> float:
        """Signed working hours from the anchor up to ``instant``."""
        day = instant.date()
        previous = day - timedelta(days=1)
        return (self.cumulative(previous) + clip_window_hours(self.window(previous), instant)
                + clip_window_hours(self.window(day), instant))

    def between(self, start: datetime, end: datetime) -> float:
        if type(start) is not datetime or type(end) is not datetime:
            raise ValidationError("工作小时差需要两个 datetime。", field="working_hours_between")
        if abs((end - start).days) > MAX_SPAN_DAYS:
            raise ValidationError(
                f"工作小时差跨度超出合理范围（不能超过 {MAX_SPAN_DAYS} 天）", field="working_hours_between",
            )
        if end == start:
            return 0.0
        return self.hours_until(end) - self.hours_until(start)


__all__ = ["MAX_SPAN_DAYS", "Window", "WindowResolver", "WorkingHoursPrefix", "clip_window_hours"]
