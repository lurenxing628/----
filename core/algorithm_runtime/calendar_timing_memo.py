"""Per-decode memo of the pure calendar timing calls made while estimating internal slots.

A slot estimate hops over busy blocks, and every hop asks the calendar the same timing
questions: adjust this instant to working time, consume the operation's effective hours,
measure the working span, and read the certified constant work window around it.
The calendar does not change while one decode runs, so those answers are pure functions
of their arguments, and measured decodes repeat 96-99% of them. The memo answers repeats
from a dict and defers everything else to the real calendar with exactly the call the
estimator would have made itself; exceptions propagate and are never memoized. Its keys are
the call arguments as the estimators pass them: naive datetimes, float hours, the batch
priority text and an operator id (text, or None for an unassigned operator).

A calendar is native when it is an instance of a registered native calendar type;
a registered type vouches for its subclasses' timing surface.
"""

import enum
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Tuple


class TimingCalendar(Protocol):
    """The calendar calls a slot estimate makes; the decode memo and the native calendar both answer them."""

    def adjust_to_working_time(self, dt: datetime, *, priority: Any, operator_id: Any) -> datetime: ...

    def add_effective_hours(self, start: datetime, hours: Any, *, priority: Any, operator_id: Any) -> datetime: ...

    def working_hours_between(self, start: datetime, end: datetime, *, priority: Any, operator_id: Any) -> float: ...

    def certified_slot_window(self, dt: datetime, *, priority: Any, operator_id: Any) -> Optional[Tuple[datetime, datetime]]: ...


class _Sentinel(enum.Enum):
    """Single-member enum: ``found is not _MISSING`` then narrows to the memoized value type."""

    MISSING = 0


_MISSING = _Sentinel.MISSING
_LIMIT = 32768
_NATIVE_CALENDAR_TYPES: Tuple[type, ...] = ()


def register_native_timing_calendar(calendar_type: type) -> None:
    """Certify a calendar type's timing methods and calendar-day arithmetic as native."""
    global _NATIVE_CALENDAR_TYPES
    if calendar_type not in _NATIVE_CALENDAR_TYPES:
        _NATIVE_CALENDAR_TYPES += (calendar_type,)


def native_timing_calendar(calendar: Any) -> bool:
    return isinstance(calendar, _NATIVE_CALENDAR_TYPES)


def _remember(memo: Dict[Any, Any], key: Any, value: Any) -> Any:
    if len(memo) >= _LIMIT:
        memo.clear()
    memo[key] = value
    return value


class MemoizedTimingCalendar:
    """The estimator-facing timing surface of one certified calendar, with memoized pure answers."""

    __slots__ = ("calendar", "_adjust", "_efficiency", "_effective_hours", "_window", "_between")

    def __init__(self, calendar: Any) -> None:
        self.calendar = calendar
        self._adjust: Dict[Tuple[Any, ...], datetime] = {}
        self._efficiency: Dict[Tuple[Any, ...], Any] = {}
        self._effective_hours: Dict[Tuple[Any, ...], datetime] = {}
        self._window: Dict[Tuple[Any, ...], Optional[Tuple[datetime, datetime]]] = {}
        self._between: Dict[Tuple[Any, ...], float] = {}

    def working_hours_between(self, start: datetime, end: datetime, *, priority: Any, operator_id: Any) -> float:
        """Signed working hours from ``start`` to ``end``; only calendars with work windows answer this."""
        key = (start, end, priority, operator_id)
        found = self._between.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return _remember(self._between, key, self.calendar.working_hours_between(start, end, priority=priority, operator_id=operator_id))

    def adjust_to_working_time(self, dt: datetime, *, priority: Any, operator_id: Any) -> datetime:
        key = (dt, priority, operator_id)
        found = self._adjust.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return _remember(self._adjust, key, self.calendar.adjust_to_working_time(dt, priority=priority, operator_id=operator_id))

    def get_efficiency(self, dt: datetime, *, operator_id: Any) -> Any:
        key = (dt, operator_id)
        found = self._efficiency.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return _remember(self._efficiency, key, self.calendar.get_efficiency(dt, operator_id=operator_id))

    def add_effective_hours(self, start: datetime, hours: Any, *, priority: Any, operator_id: Any) -> datetime:
        key = (start, hours, priority, operator_id)
        found = self._effective_hours.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return _remember(self._effective_hours, key, self.calendar.add_effective_hours(start, hours, priority=priority, operator_id=operator_id))

    def certified_slot_window(self, dt: datetime, *, priority: Any, operator_id: Any) -> Optional[Tuple[datetime, datetime]]:
        """The underlying certificate, or None outside a constant work window."""
        key = (dt, priority, operator_id)
        found = self._window.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return _remember(self._window, key, self.calendar.certified_slot_window(dt, priority=priority, operator_id=operator_id))


__all__ = ["MemoizedTimingCalendar", "TimingCalendar", "native_timing_calendar", "register_native_timing_calendar"]
