"""One wall-clock occupancy definition for reports and workbench projections.

Inputs are already selected from one plan/source and one resource. Missing actual
intervals stay missing: this calculator never substitutes planned timestamps.
Efficiency-weighted processing hours are deliberately outside this definition.
"""

from bisect import bisect_right

from .plan_calendar_intervals import IntervalIndex, intersection, segments, union

METRIC_VERSION = "available_occupancy_v1"


class _WeightedIndex:
    def __init__(self, rows):
        self.rows = rows
        self.starts = [start for start, _, _ in rows]
        self.prefix = [0.0]
        for start, end, count in rows:
            self.prefix.append(self.prefix[-1] + (end - start).total_seconds() * count)

    def _before(self, at):
        index = bisect_right(self.starts, at) - 1
        if index < 0:
            return 0.0
        start, end, count = self.rows[index]
        return self.prefix[index] + (min(at, end) - start).total_seconds() * count

    def hours_between(self, start, end):
        return (self._before(end) - self._before(start)) / 3600.0


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
        self.available = IntervalIndex(available)
        self.occupied = IntervalIndex(intersection(occupied, self.available.intervals))
        self.load = _WeightedIndex(_available_segments(swept, self.available.intervals))

    def hours_between(self, start, end):
        """(capacity, occupied, summed load) hours inside the window."""
        return (self.available.hours_between(start, end), self.occupied.hours_between(start, end),
                self.load.hours_between(start, end))


class ResourceUtilizationMetrics:
    """Build once; whole-window and daily queries use the same indexed intervals."""

    def __init__(self, intervals, available, *, source="planned"):
        if source not in ("planned", "actual"):
            raise ValueError("Utilization source must be planned or actual")
        intervals = list(intervals)
        if any(start > end for start, end in intervals):
            raise ValueError("Invalid resource task interval")
        self.source = source
        occupied, swept = union(intervals), segments(intervals)
        self.span = IntervalIndex(occupied)
        self.span_load = _WeightedIndex(swept)
        self.span_overlap = IntervalIndex([(start, end) for start, end, count in swept if count > 1])
        # None means the resource's calendar is unknown, never that it has zero capacity.
        self.calendar = _CalendarIndexes(available, occupied, swept) if available is not None else None

    def window(self, start, end):
        if start > end:
            raise ValueError("Invalid utilization window")
        span = self.span.hours_between(start, end)
        if self.calendar is None:
            capacity = occupied = load = overlap = outside = ratio = None
        else:
            capacity, occupied, load = self.calendar.hours_between(start, end)
            overlap, outside = load - occupied, span - occupied
            ratio = occupied / capacity if capacity > 0 else None
        result = {
            "available_hours": capacity, "occupied_hours": occupied,
            "summed_load_hours": load,
            "overlap_hours": overlap,
            "outside_calendar_hours": outside,
            "utilization_ratio": ratio,
            "span_occupied_hours": span, "span_summed_hours": self.span_load.hours_between(start, end),
            "span_overlap_hours": self.span_overlap.hours_between(start, end),
        }
        return {**{key: round(value, 6) if value is not None else None for key, value in result.items()},
                "metric_version": METRIC_VERSION, "source": self.source,
                "reason": "calendar_unavailable" if capacity is None else "zero_available_capacity" if capacity == 0 else None}
