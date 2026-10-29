"""Per-decode memo of the pure calendar timing calls made while estimating internal slots.

A slot estimate hops over busy blocks, and every hop asks the calendar the same timing
questions: adjust this instant to working time, consume the operation's effective hours,
measure the working span, and read the certified constant work window around it.
The calendar does not change while one decode runs, so those answers are pure functions
of their arguments, and measured decodes repeat 96-99% of them. The memo answers repeats
from a dict and defers everything else to the real calendar with exactly the call the
estimator would have made itself; exceptions propagate and are never memoized.
"""

import enum
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple


class _Sentinel(enum.Enum):
    """Single-member enum: ``found is not _MISSING`` then narrows to the memoized value type."""

    MISSING = 0


_MISSING = _Sentinel.MISSING
_LIMIT = 32768
_GUARDS: Dict[type, Callable[[Any], bool]] = {}
_CALENDAR_DAY_GUARDS: Dict[type, Callable[[Any], bool]] = {}


def make_lineage_timing_guard(base: type) -> Callable[[Any], bool]:
    return lambda calendar: isinstance(calendar, base)


def register_calendar_timing_guard(
    calendar_type: type, guard: Callable[[Any], bool], *, calendar_days_guard: Callable[[Any], bool],
) -> None:
    _GUARDS[calendar_type] = guard
    _CALENDAR_DAY_GUARDS[calendar_type] = calendar_days_guard


def native_timing_calendar(calendar: Any, *, include_calendar_days: bool = False) -> bool:
    """The nearest registered guard in the calendar's lineage certifies its timing methods as native."""
    for entry in type(calendar).__mro__:
        guard = _GUARDS.get(entry)
        if guard is not None:
            if not guard(calendar):
                return False
            if not include_calendar_days:
                return True
            return _CALENDAR_DAY_GUARDS[entry](calendar)
    return False


def _plain_text(value: Any) -> bool:
    return value is None or type(value) is str


def _remember(memo: Dict[Any, Any], key: Any, value: Any) -> Any:
    if len(memo) >= _LIMIT:
        memo.clear()
    memo[key] = value
    return value


class MemoizedTimingCalendar:
    """The estimator-facing timing surface of one certified calendar, with memoized pure answers."""

    __slots__ = ("calendar", "hits", "misses", "_adjust", "_efficiency", "_effective_hours", "_window", "_between")

    def __init__(self, calendar: Any) -> None:
        self.calendar = calendar
        self.hits = 0
        self.misses = 0
        self._adjust: Dict[Tuple[Any, ...], datetime] = {}
        self._efficiency: Dict[Tuple[Any, ...], Any] = {}
        self._effective_hours: Dict[Tuple[Any, ...], datetime] = {}
        self._window: Dict[Tuple[Any, ...], Optional[Tuple[datetime, datetime]]] = {}
        self._between: Dict[Tuple[Any, ...], float] = {}

    def working_hours_between(self, start: datetime, end: datetime, *, priority: Any, operator_id: Any) -> float:
        """Signed working hours from ``start`` to ``end``; only calendars with work windows answer this."""
        if (type(start) is not datetime or type(end) is not datetime
                or not _plain_text(priority) or not _plain_text(operator_id)):
            return self.calendar.working_hours_between(start, end, priority=priority, operator_id=operator_id)
        key = (start, end, priority, operator_id)
        found = self._between.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._between, key, self.calendar.working_hours_between(start, end, priority=priority, operator_id=operator_id))

    def adjust_to_working_time(self, dt: datetime, *, priority: Any, operator_id: Any) -> datetime:
        if type(dt) is not datetime or not _plain_text(priority) or not _plain_text(operator_id):
            return self.calendar.adjust_to_working_time(dt, priority=priority, operator_id=operator_id)
        key = (dt, priority, operator_id)
        found = self._adjust.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._adjust, key, self.calendar.adjust_to_working_time(dt, priority=priority, operator_id=operator_id))

    def get_efficiency(self, dt: datetime, *, operator_id: Any) -> Any:
        if type(dt) is not datetime or not _plain_text(operator_id):
            return self.calendar.get_efficiency(dt, operator_id=operator_id)
        key = (dt, operator_id)
        found = self._efficiency.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._efficiency, key, self.calendar.get_efficiency(dt, operator_id=operator_id))

    def add_effective_hours(self, start: datetime, hours: Any, *, priority: Any, operator_id: Any) -> datetime:
        if type(start) is not datetime or type(hours) is not float or not _plain_text(priority) or not _plain_text(operator_id):
            return self.calendar.add_effective_hours(start, hours, priority=priority, operator_id=operator_id)
        key = (start, hours, priority, operator_id)
        found = self._effective_hours.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._effective_hours, key, self.calendar.add_effective_hours(start, hours, priority=priority, operator_id=operator_id))

    def certified_slot_window(self, dt: datetime, *, priority: Any, operator_id: Any) -> Optional[Tuple[datetime, datetime]]:
        """The underlying certificate, or None for calendars that offer none; validated by the caller as before."""
        if type(dt) is not datetime or not _plain_text(priority) or not _plain_text(operator_id):
            return self._certify(dt, priority, operator_id)
        key = (dt, priority, operator_id)
        found = self._window.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._window, key, self._certify(dt, priority, operator_id))

    def _certify(self, dt: datetime, priority: Any, operator_id: Any) -> Optional[Tuple[datetime, datetime]]:
        certify = getattr(self.calendar, "certified_slot_window", None)
        if certify is None:
            return None
        return certify(dt, priority=priority, operator_id=operator_id)


__all__ = [
    "MemoizedTimingCalendar", "make_lineage_timing_guard",
    "native_timing_calendar", "register_calendar_timing_guard",
]
