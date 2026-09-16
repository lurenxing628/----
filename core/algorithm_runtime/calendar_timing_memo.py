"""Per-decode memo of the pure calendar timing calls made while estimating internal slots.

A slot estimate hops over busy blocks, and every hop asks the calendar the same four
questions: adjust this instant to working time, the efficiency at that instant, the end
after adding the operation's hours, and the certified constant work window around it.
The calendar does not change while one decode runs, so those answers are pure functions
of their arguments, and measured decodes repeat 96-99% of them. The memo answers repeats
from a dict and defers everything else to the real calendar with exactly the call the
estimator would have made itself; exceptions propagate and are never memoized.

Only calendars whose timing methods are proven native qualify. Each calendar type
registers a guard that certifies neither the class lineage nor the instance overrides
those methods, so an instrumented calendar keeps receiving every call. The guard is
re-checked every SGS round by the owner of the memo.
"""

import operator
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from .static_attribute import static_attribute

_MISSING = object()
_LIMIT = 32768
_GUARDS: Dict[type, Callable[[Any], bool]] = {}
TIMING_METHODS = ("get_efficiency", "adjust_to_working_time", "add_working_hours", "certified_slot_window")
ACCESSOR_HOOKS = ("__getattribute__", "__getattr__")


def member_identity_guard(cls: type, names: Sequence[str]) -> Callable[[], bool]:
    """True while every named member of ``cls`` is the object captured now and its lineage is intact."""
    original = tuple(map(cls.__dict__.get, names))
    lineage = cls.__mro__

    def unchanged() -> bool:
        return cls.__mro__ is lineage and all(map(operator.is_, map(cls.__dict__.get, names), original))

    return unchanged


def make_lineage_timing_guard(base: type, methods: Sequence[str]) -> Callable[[Any], bool]:
    """Instances of ``base`` or of subclasses that override none of ``methods`` or the accessor hooks."""
    names = tuple(methods) + ACCESSOR_HOOKS
    base_unchanged = member_identity_guard(base, names + ("__dict__",))
    overrides = frozenset(names)
    instance_overrides = frozenset(methods)

    def supported(calendar: Any) -> bool:
        kind = type(calendar)
        if type(kind) is not type:
            return False
        for entry in kind.__mro__:
            if entry is base:
                break
            if not entry.__dict__.keys().isdisjoint(overrides):
                return False
        else:
            return False
        if not base_unchanged():
            return False
        try:
            instance_dict = object.__getattribute__(calendar, "__dict__")
        except AttributeError:
            return True
        return type(instance_dict) is dict and instance_dict.keys().isdisjoint(instance_overrides)

    return supported


def register_calendar_timing_guard(calendar_type: type, guard: Callable[[Any], bool]) -> None:
    _GUARDS[calendar_type] = guard


def native_timing_calendar(calendar: Any) -> bool:
    """The nearest registered guard in the calendar's lineage certifies its timing methods as native."""
    kind = type(calendar)
    if type(kind) is not type:
        return False
    for entry in kind.__mro__:
        guard = _GUARDS.get(entry)
        if guard is not None:
            return guard(calendar)
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

    __slots__ = ("calendar", "hits", "misses", "_adjust", "_efficiency", "_hours", "_window")

    def __init__(self, calendar: Any) -> None:
        self.calendar = calendar
        self.hits = 0
        self.misses = 0
        self._adjust: Dict[Tuple[Any, ...], datetime] = {}
        self._efficiency: Dict[Tuple[Any, ...], Any] = {}
        self._hours: Dict[Tuple[Any, ...], datetime] = {}
        self._window: Dict[Tuple[Any, ...], Optional[Tuple[datetime, datetime]]] = {}

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

    def add_working_hours(self, start: datetime, hours: Any, *, priority: Any, operator_id: Any) -> datetime:
        if type(start) is not datetime or type(hours) is not float or not _plain_text(priority) or not _plain_text(operator_id):
            return self.calendar.add_working_hours(start, hours, priority=priority, operator_id=operator_id)
        key = (start, hours, priority, operator_id)
        found = self._hours.get(key, _MISSING)
        if found is not _MISSING:
            self.hits += 1
            return found
        self.misses += 1
        return _remember(self._hours, key, self.calendar.add_working_hours(start, hours, priority=priority, operator_id=operator_id))

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
        if static_attribute(self.calendar, "certified_slot_window") is None:
            return None
        return self.calendar.certified_slot_window(dt, priority=priority, operator_id=operator_id)


__all__ = [
    "ACCESSOR_HOOKS", "MemoizedTimingCalendar", "TIMING_METHODS", "make_lineage_timing_guard", "member_identity_guard",
    "native_timing_calendar", "register_calendar_timing_guard",
]
