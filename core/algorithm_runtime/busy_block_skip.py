"""Skip only fully occupied time inside a certified constant native work window."""

from datetime import datetime

from .downtime import SegmentOverlapIndex


def _native_union_end(segment_groups, start, limit):
    """Extend only continuous occupancy; even a microsecond gap ends the walk."""
    cursor = start
    while cursor < limit:
        next_cursor = max(
            (end for index in segment_groups for end in (index.covered_end(cursor),) if end is not None and cursor < end <= limit),
            default=cursor,
        )
        if next_cursor == cursor:
            return cursor
        cursor = next_cursor
    return cursor


def _native_indexes(segment_groups):
    return all(isinstance(index, SegmentOverlapIndex) and index.has_native_coverage() for index in segment_groups)


def _certified_window(calendar, earliest, priority, operator_id):
    certify = getattr(calendar, "certified_slot_window", None)
    if certify is None:
        return None
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
    next_shift = max(
        (end for index in segment_groups for end in (index.covered_end(shift_to),) if end is not None and shift_to < end <= window[1]),
        default=shift_to,
    )
    if _can_extend_union(segment_groups, shift_to, next_shift):
        return _native_union_end(segment_groups, next_shift, window[1])
    return next_shift
