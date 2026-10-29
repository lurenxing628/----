"""One wall-clock occupancy definition for reports and workbench projections.

Inputs are planned intervals already selected from one plan/source and one resource.
Efficiency-weighted processing hours are deliberately outside this definition.
"""

from bisect import bisect_right
from itertools import tee
from typing import Optional

from .plan_calendar_intervals import (
    HOUR_MICROSECONDS,
    IntervalIndex,
    intersection,
    interval_microseconds,
    segments,
    union_sorted,
)

METRIC_VERSION = "available_occupancy_v1"


class _WeightedIndex:
    def __init__(self, rows):
        self.rows = rows
        self.starts = [start for start, _, _ in rows]
        self.prefix = [0]
        for start, end, count in rows:
            self.prefix.append(self.prefix[-1] + interval_microseconds(start, end) * count)

    def _at_index(self, index, at):
        if index < 0:
            return 0
        start, end, count = self.rows[index]
        if at >= end:
            return self.prefix[index + 1]
        return self.prefix[index] + interval_microseconds(start, at) * count

    def _before(self, at):
        return self._at_index(bisect_right(self.starts, at) - 1, at)

    def prefix_values_at_sorted(self, points):
        """Consume caller-ordered points as cumulative microseconds, including repeats."""
        index = -1
        for at in points:
            while index + 1 < len(self.starts) and self.starts[index + 1] <= at:
                index += 1
            yield self._at_index(index, at)

    def hours_between(self, start, end):
        return (self._before(end) - self._before(start)) / HOUR_MICROSECONDS


def _available_segments(swept, available):
    result, index = [], 0
    for start, end, count in swept:
        while index < len(available) and available[index][1] <= start:
            index += 1
        current = index
        while current < len(available) and available[current][0] < end:
            low, high = max(start, available[current][0]), min(end, available[current][1])
            if low < high:
                result.append((low, high, count))
            current += 1
    return result


class _CalendarIndexes:
    """Calendar-bound views of one resource; they exist together or not at all."""

    def __init__(self, available, occupied, swept):
        self.available = IntervalIndex.from_normalized(available)
        self.occupied = IntervalIndex.from_normalized(intersection(occupied, self.available.intervals))
        self.load = _WeightedIndex(_available_segments(swept, self.available.intervals))

    def hours_between(self, start, end):
        """(capacity, occupied, summed load) hours inside the window."""
        return (self.available.hours_between(start, end), self.occupied.hours_between(start, end),
                self.load.hours_between(start, end))


class ResourceUtilizationMetrics:
    """Build once from normalized availability; whole-window and daily queries use the same indexed intervals."""

    @classmethod
    def from_normalized_availability(cls, intervals, available):
        """Consume internal unioned availability directly; None keeps unknown capacity."""
        metrics = cls.__new__(cls)
        metrics._initialize(intervals, available)
        return metrics

    def _initialize(self, intervals, available):
        intervals = list(intervals)
        if any(start > end for start, end in intervals):
            raise ValueError("Invalid resource task interval")
        swept = segments(intervals)
        occupied = union_sorted((start, end) for start, end, _ in swept)
        self.segments = swept
        self.span = IntervalIndex.from_normalized(occupied)
        self.span_load = _WeightedIndex(swept)
        self.span_overlap = IntervalIndex.from_normalized(union_sorted(
            (start, end) for start, end, count in swept if count > 1))
        # None means the resource's calendar is unknown, never that it has zero capacity.
        self.calendar = _CalendarIndexes(available, occupied, swept) if available is not None else None

    def window(self, start, end, *, precision: Optional[int] = 6):
        if start > end:
            raise ValueError("Invalid utilization window")
        span = self.span.hours_between(start, end)
        if self.calendar is None:
            capacity = occupied = load = None
        else:
            capacity, occupied, load = self.calendar.hours_between(start, end)
        return self._window_result(span, self.span_load.hours_between(start, end), self.span_overlap.hours_between(start, end),
                                   capacity, occupied, load, precision=precision)

    def windows_at_boundaries(self, boundaries, *, precision: Optional[int] = None):
        """Yield adjacent ordered windows from the existing cumulative-second indexes."""
        indexes = (self.span, self.span_load, self.span_overlap)
        if self.calendar is not None:
            indexes += (self.calendar.available, self.calendar.occupied, self.calendar.load)
        points = tee(boundaries, len(indexes))
        prefixes = zip(*(index.prefix_values_at_sorted(ordered) for index, ordered in zip(indexes, points)))
        previous = next(prefixes, None)
        if previous is None:
            return
        for current in prefixes:
            values = tuple((right - left) / HOUR_MICROSECONDS for left, right in zip(previous, current))
            if self.calendar is None:
                values += (None, None, None)
            yield self._window_result(*values, precision=precision)
            previous = current

    def _window_result(self, span, span_load, span_overlap, capacity, occupied, load, *, precision):
        if capacity is None:
            overlap = outside = ratio = None
        else:
            overlap, outside = load - occupied, span - occupied
            ratio = occupied / capacity if capacity > 0 else None
        result = {
            "available_hours": capacity, "occupied_hours": occupied,
            "summed_load_hours": load,
            "overlap_hours": overlap,
            "outside_calendar_hours": outside,
            "utilization_ratio": ratio,
            "span_occupied_hours": span, "span_summed_hours": span_load,
            "span_overlap_hours": span_overlap,
        }
        if precision is not None:
            result = {key: round(value, precision) if value is not None else value for key, value in result.items()}
        result.update(metric_version=METRIC_VERSION, source="planned",
                      reason="calendar_unavailable" if capacity is None else "zero_available_capacity" if capacity == 0 else None)
        return result
