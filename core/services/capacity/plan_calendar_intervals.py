"""Half-open interval algebra shared by plan calendar and occupancy projections."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime

from core.shared.local_datetime import format_local_datetime, parse_local_datetime


def instant(value):
    parsed = parse_local_datetime(value)
    if parsed is None:
        raise ValueError("Invalid local plan/calendar time")
    if type(parsed) is datetime and not parsed.fold:
        return parsed
    # The original text round trip normalized fold and datetime subclasses.
    return datetime.fromisoformat(format_local_datetime(parsed))


def wire(value):
    return value.isoformat()


def union(intervals):
    return _union_sorted(sorted(intervals))


def _union_sorted(intervals):
    """Merge sorted input in one pass, including adjacent positive intervals."""
    result = []
    for start, end in intervals:
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
        self._build_prefix(union(intervals))

    @classmethod
    def from_normalized(cls, intervals):
        """Index internal sorted, positive, disjoint intervals without another union."""
        index = cls.__new__(cls)
        index._build_prefix(intervals)
        return index

    def _build_prefix(self, intervals):
        self.intervals = list(intervals)
        self.starts = []
        self.prefix = [0.0]
        for start, end in self.intervals:
            self.starts.append(start)
            self.prefix.append(self.prefix[-1] + (end - start).total_seconds())

    def _at_index(self, index, at):
        if index < 0:
            return 0.0
        start, end = self.intervals[index]
        if at >= end:
            return self.prefix[index + 1]
        return self.prefix[index] + (at - start).total_seconds()

    def _before(self, at):
        return self._at_index(bisect_right(self.starts, at) - 1, at)

    def prefix_values_at_sorted(self, points):
        """Consume caller-ordered points as cumulative seconds, including repeats."""
        index = -1
        for at in points:
            while index + 1 < len(self.starts) and self.starts[index + 1] <= at:
                index += 1
            yield self._at_index(index, at)

    def hours_between(self, start, end):
        return (self._before(end) - self._before(start)) / 3600.0

    def seconds_and_count_between(self, start, end):
        """Return overlap seconds and the number of intersecting stored intervals."""
        if not self.intervals or end <= start:
            return 0.0, 0
        first = max(0, bisect_right(self.starts, start) - 1)
        last = bisect_left(self.starts, end)
        if first < last and self.intervals[first][1] <= start:
            first += 1
        if first >= last:
            return 0.0, 0
        seconds = self.prefix[last] - self.prefix[first]
        if start > self.intervals[first][0]:
            seconds -= (start - self.intervals[first][0]).total_seconds()
        if end < self.intervals[last - 1][1]:
            seconds -= (self.intervals[last - 1][1] - end).total_seconds()
        return seconds, last - first

    def contains(self, at, *, ending=False):
        """A finish may touch a period's end; a start must be inside [start,end)."""
        index = (bisect_left if ending else bisect_right)(self.starts, at) - 1
        if index < 0:
            return False
        start, end = self.intervals[index]
        return start < at <= end if ending else start <= at < end


def public_intervals(intervals):
    return [{"start": wire(start), "end": wire(end)} for start, end in intervals]
