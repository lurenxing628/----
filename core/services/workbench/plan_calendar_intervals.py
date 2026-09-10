"""Half-open interval algebra shared by plan calendar and occupancy projections."""

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime

from data.repositories.schedule_time_sql import parse_dt_for_sql


def instant(value):
    parsed = parse_dt_for_sql(value)
    if parsed is None:
        raise ValueError("Invalid local plan/calendar time")
    return datetime.fromisoformat(parsed)


def wire(value):
    return value.isoformat(timespec="seconds")


def union(intervals):
    result = []
    for start, end in sorted(intervals):
        if start >= end:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def intersection(left, right):
    """Inputs are sorted disjoint intervals; runtime is linear in both lengths."""
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if start < end:
            result.append((start, end))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return result


def hours(intervals):
    return sum((end - start).total_seconds() for start, end in intervals) / 3600.0


def segments(intervals):
    """Sweep overlap multiplicity without enumerating task pairs or active sets."""
    events = defaultdict(int)
    for start, end in intervals:
        if start < end:
            events[start] += 1
            events[end] -= 1
    result, active, previous = [], 0, None
    for at, delta in sorted(events.items()):
        if previous is not None and previous < at and active:
            if result and result[-1][1] == previous and result[-1][2] == active:
                result[-1] = (result[-1][0], at, active)
            else:
                result.append((previous, at, active))
        active += delta
        previous = at
    return result


class IntervalIndex:
    """O(log W) per task intersection duration after O(W) prefix construction."""

    def __init__(self, intervals):
        self.intervals = union(intervals)
        self.starts = [start for start, _ in self.intervals]
        self.prefix = [0.0]
        for start, end in self.intervals:
            self.prefix.append(self.prefix[-1] + (end - start).total_seconds())

    def _before(self, at):
        index = bisect_right(self.starts, at) - 1
        if index < 0:
            return 0.0
        start, end = self.intervals[index]
        return self.prefix[index] + (min(at, end) - start).total_seconds()

    def hours_between(self, start, end):
        return (self._before(end) - self._before(start)) / 3600.0


def public_intervals(intervals):
    return [{"start": wire(start), "end": wire(end)} for start, end in intervals]

