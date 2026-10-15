"""Prepare immutable minute offsets once, using the shared period rules."""

from datetime import datetime

from core.models.calendar_periods import period_windows


def period_offsets(periods):
    if periods is None:
        return None
    base = datetime(2000, 1, 1)
    return tuple((int((start - base).total_seconds() // 60), int((end - base).total_seconds() // 60))
                 for start, end in period_windows(base.date(), periods))


def offset_hours(offsets):
    return sum(end - start for start, end in offsets) / 60
