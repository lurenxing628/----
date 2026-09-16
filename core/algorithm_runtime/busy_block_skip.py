"""Skip only fully occupied time inside a certified constant native work window."""

from datetime import datetime

from .downtime import SegmentOverlapIndex
from .static_attribute import static_attribute

_NATIVE_COVERED_END = SegmentOverlapIndex.covered_end
_NATIVE_COVERAGE_CHECK = SegmentOverlapIndex.has_native_coverage


def _native_union_end(segment_groups, start, limit):
    """Extend only continuous occupancy; even a microsecond gap ends the walk."""
    cursor = start
    while cursor < limit:
        ends = [index.covered_end(cursor) for index in segment_groups]
        next_cursor = max((end for end in ends if end is not None and cursor < end <= limit), default=cursor)
        if next_cursor == cursor:
            return cursor
        cursor = next_cursor
    return cursor


def _native_indexes(segment_groups):
    if (SegmentOverlapIndex.covered_end is not _NATIVE_COVERED_END
            or SegmentOverlapIndex.has_native_coverage is not _NATIVE_COVERAGE_CHECK):
        return False
    return all(type(index) is SegmentOverlapIndex and index.has_native_coverage() for index in segment_groups)


def _certified_window(calendar, earliest, priority, operator_id):
    # An overlay's __getattr__ must not borrow its underlying calendar's proof.
    if static_attribute(calendar, "certified_slot_window") is None:
        return None
    certify = calendar.certified_slot_window
    window = certify(earliest, priority=priority, operator_id=operator_id)
    if window is None:
        return None
    if (type(window) is not tuple or len(window) != 2 or any(type(value) is not datetime for value in window)
            or not window[0] <= earliest < window[1]):
        raise RuntimeError("Calendar returned an invalid constant work-window certificate")
    return window


def _can_extend_union(segment_groups, shift_to, next_shift):
    return (next_shift > shift_to and type(segment_groups) in (tuple, list)
            and type(shift_to) is datetime and shift_to.tzinfo is None and _native_indexes(segment_groups))


def advance_busy_block(calendar, *, earliest, shift_to, segment_groups, total_base, priority, operator_id, abort_after):
    if total_base <= 0 or abort_after is not None:
        return shift_to
    window = _certified_window(calendar, earliest, priority, operator_id)
    if window is None or shift_to >= window[1]:
        return shift_to
    covered = [index.covered_end(shift_to) for index in segment_groups]
    reachable = [end for end in covered if end is not None and shift_to < end <= window[1]]
    next_shift = max(reachable, default=shift_to)
    if _can_extend_union(segment_groups, shift_to, next_shift):
        return _native_union_end(segment_groups, next_shift, window[1])
    return next_shift
