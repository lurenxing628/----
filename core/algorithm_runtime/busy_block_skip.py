"""Skip only fully occupied time inside a certified constant native work window."""

from .calendar_timing_memo import MemoizedTimingCalendar, native_timing_calendar


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


def _certified_window(calendar, earliest, priority, operator_id):
    """Only native calendars, directly or behind the decode memo, certify constant work windows."""
    if not (isinstance(calendar, MemoizedTimingCalendar) or native_timing_calendar(calendar)):
        return None
    return calendar.certified_slot_window(earliest, priority=priority, operator_id=operator_id)


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
    if next_shift > shift_to:
        return _native_union_end(segment_groups, next_shift, window[1])
    return next_shift
