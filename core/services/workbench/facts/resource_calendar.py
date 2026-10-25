"""One resource's saved calendar geometry, normalized once and shared by task indexes.

Days are clipped to the selected window; unknown calendar days stay unknown and
never become zero capacity.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, NamedTuple, Tuple

from core.services.capacity.plan_calendar_intervals import instant, intersection, union


def natural_days(low, high):
    if low == high:
        yield low, high
    while low < high:
        boundary = high if low.date() == date.max else datetime.combine(low.date() + timedelta(days=1), time.min)
        end = min(high, boundary)
        yield low, end
        low = end


def resource_period_bounds(start, end, grain="day"):
    """Clip natural hours, days or Monday-based weeks to the selected window."""
    low, high = instant(start), instant(end)
    if grain == "day" or low == high:
        yield from natural_days(low, high)
        return
    while low < high:
        if grain == "hour":
            step = low.replace(minute=0, second=0, microsecond=0) - low + timedelta(hours=1)
        elif grain == "week":
            step = datetime.combine(low.date(), time.min) - low + timedelta(days=7 - low.weekday())
        else:
            raise ValueError("Expected hour, day or week resource grain")
        stop = low + min(high - low, step)
        yield low, stop
        low = stop


def calendar_days(calendar, low, high) -> List[Dict[str, Any]]:
    if calendar is not None and "days" in calendar:
        return calendar["days"]
    # Legacy/current snapshot adapters supply the same explicit full-window
    # calendar projection. Its capacity state applies to each clipped day.
    available = calendar is not None and calendar["state"] == "available"
    windows = calendar["windows"] if available else None
    issues = calendar.get("issues", []) if calendar is not None else [
        {"code": "calendar_unavailable", "message": "保存的资源班表缺项，容量未知。"}]
    return [{"date": start.date().isoformat(), "start": start.isoformat(), "end": end.isoformat(),
             "state": "available" if available else "unavailable", "windows": windows, "issues": issues}
            for start, end in natural_days(low, high)]


class CalendarDay(NamedTuple):
    date: str
    low: datetime
    high: datetime
    available: bool
    windows: List[Tuple[datetime, datetime]]
    shifts: List[Tuple[datetime, datetime, str]]
    issues: List[Dict[str, Any]]


class ResourceCalendar:
    """One resource's calendar geometry, shared by all compared task indexes."""

    def __init__(self, calendar, low, high, *, parse_time=None):
        parse_time = instant if parse_time is None else parse_time
        self.days = []
        for row in calendar_days(calendar, low, high):
            first, last = parse_time(row["start"]), parse_time(row["end"])
            available = row["state"] == "available"
            shifts = []
            for window in row["windows"] if available else []:
                if window["allow_normal"] or window["allow_urgent"]:
                    start, end = parse_time(window["start"]), parse_time(window["end"])
                    shifts.append((start, end, window.get("policy_date") or start.date().isoformat()))
            self.days.append(CalendarDay(row["date"], first, last, available,
                union((start, end) for start, end, _ in shifts), shifts, row.get("issues", [])))
        self.days.sort(key=lambda day: (day.low, day.high))
        bounds = iter(natural_days(low, high))
        self.natural_day_window = low < high and all(
            next(bounds, None) == (day.low, day.high) and day.date == day.low.date().isoformat()
            for day in self.days) and next(bounds, None) is None
        self.starts = [day.low for day in self.days]
        self.ends = [day.high for day in self.days]
        self._periods = {}
        self.known_days = [day for day in self.days if day.available]
        self.windows = union(value for day in self.known_days for value in day.windows)
        self.known_coverage = union((day.low, day.high) for day in self.known_days)

    def days_in(self, low, high):
        """Days overlapping [low, high], clipped to it; a point keeps the days it touches."""
        if low == high:
            first, last = bisect_left(self.ends, low), bisect_right(self.starts, high)
        else:
            first, last = bisect_right(self.ends, low), bisect_left(self.starts, high)
        return [day if low <= day.low and day.high <= high else day._replace(low=max(low, day.low), high=min(high, day.high))
                for day in self.days[first:last]]

    def periods_between(self, grain, low, high):
        """Cached period buckets: shifts group by policy date; rest and unknown days stay whole."""
        key = grain, low, high
        if key in self._periods:
            return self._periods[key]
        bounds = []
        if grain == "shift":
            groups = defaultdict(list)
            for day in self.days_in(low, high):
                for start, end, policy_date in day.shifts:
                    first, last = max(low, day.low, start), min(high, day.high, end)
                    if first < last:
                        groups[policy_date].append((first, last))
                if not day.available or not intersection(day.windows, [(day.low, day.high)]):
                    bounds.append((day.low, day.high, day.date, "rest" if day.available else "unknown"))
            bounds.extend((first, last, policy_date, None)
                          for policy_date, values in groups.items() for first, last in union(values))
            bounds.sort(key=lambda row: (row[0], row[1]))
        else:
            bounds = [(first, last, first.date().isoformat(), None) for first, last in resource_period_bounds(low, high, grain)]
        self._periods[key] = bounds
        return bounds


def normalize_resource_calendar(calendar, start, end, *, parse_time=None):
    """Normalize the common saved calendar once; raw legacy callers use this too."""
    if isinstance(calendar, ResourceCalendar):
        return calendar
    parse_time = instant if parse_time is None else parse_time
    return ResourceCalendar(calendar, parse_time(start), parse_time(end), parse_time=parse_time)
