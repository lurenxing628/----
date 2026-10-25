"""Calendar business contents read for SGS decode checkpoint certificates.

Rows come back as nested tuples in a fixed query order. Query order, column order
and raw storage values are all part of the certificate; rows are never mapped to
dicts or models here.
"""

from __future__ import annotations

from typing import Any, Tuple

from .base_repo import BaseRepository

# Include every field read by CalendarEngine / OperatorShiftCalendar; names and remarks do not affect time.
_BUSINESS_FIELDS = (
    ("WorkbenchCalendarDefaults", ("singleton", "periods_json"), ("singleton",)),
    (
        "WorkCalendar",
        ("date", "day_type", "shift_start", "shift_end", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "periods_json"),
        ("date",),
    ),
    (
        "OperatorCalendar",
        ("operator_id", "date", "day_type", "shift_start", "shift_end", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "periods_json"),
        ("operator_id", "date"),
    ),
    ("WorkbenchOperatorProfiles", ("operator_id", "shift_profile_id"), ("operator_id",)),
    ("WorkbenchShiftProfiles", ("profile_id", "anchor_date", "cycle_days", "status"), ("profile_id",)),
    ("WorkbenchShiftPatternDays", ("profile_id", "day_offset", "is_rest", "shift_start", "shift_end"), ("profile_id", "day_offset")),
    ("WorkbenchShiftDayPeriods", ("profile_id", "day_offset", "periods_json"), ("profile_id", "day_offset")),
)


def _storage_order(value):
    # SQLite ORDER BY compares storage classes before their native values.
    if value is None:
        return (0,)
    if isinstance(value, (int, float)):
        return 1, value
    if isinstance(value, bytes):
        return 3, value
    return 2, str(value)


class CalendarCheckpointRepository(BaseRepository):
    def calendar_signature_rows(self, *, capture) -> Tuple[Tuple[Tuple[Any, ...], ...], ...]:
        """One tuple of row tuples per business table, preserving query fields and order."""
        result = []
        for table, fields, order in _BUSINESS_FIELDS:
            if capture is None:
                rows = self.execute(f"SELECT {','.join(fields)} FROM {table} ORDER BY {','.join(order)}").fetchall()
                result.append(tuple(tuple(row) for row in rows))
            else:
                originals = sorted(
                    capture.business_table(table),
                    key=lambda row: tuple(_storage_order(row[field]) for field in order),
                )
                result.append(tuple(tuple(row[field] for field in fields) for row in originals))
        return tuple(result)
