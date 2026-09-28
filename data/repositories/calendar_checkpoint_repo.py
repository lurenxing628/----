"""Calendar business contents read for SGS decode checkpoint certificates.

Rows come back as nested tuples in a fixed query order. The caller hashes their
repr, so query order, column order and raw storage values are all part of the
certificate; rows are never mapped to dicts or models here.
"""

from __future__ import annotations

from typing import Any, Tuple

from .base_repo import BaseRepository

# Include every field read by CalendarEngine / OperatorShiftCalendar; names and remarks do not affect time.
_BUSINESS_QUERIES = (
    "SELECT singleton,periods_json FROM WorkbenchCalendarDefaults ORDER BY singleton",
    "SELECT date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,periods_json FROM WorkCalendar ORDER BY date",
    "SELECT operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,periods_json FROM OperatorCalendar ORDER BY operator_id,date",
    "SELECT operator_id,shift_profile_id FROM WorkbenchOperatorProfiles ORDER BY operator_id",
    "SELECT profile_id,anchor_date,cycle_days,status FROM WorkbenchShiftProfiles ORDER BY profile_id",
    "SELECT profile_id,day_offset,is_rest,shift_start,shift_end FROM WorkbenchShiftPatternDays ORDER BY profile_id,day_offset",
    "SELECT profile_id,day_offset,periods_json FROM WorkbenchShiftDayPeriods ORDER BY profile_id,day_offset",
)


class CalendarCheckpointRepository(BaseRepository):
    def calendar_signature_rows(self) -> Tuple[Tuple[Tuple[Any, ...], ...], ...]:
        """One tuple of row tuples per business query, in _BUSINESS_QUERIES order."""
        return tuple(tuple(tuple(row) for row in self.execute(query).fetchall()) for query in _BUSINESS_QUERIES)
