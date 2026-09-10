"""Raw global calendar presence for a read-only, date-keyed summary."""

from .base_repo import BaseRepository


class WorkbenchResourceSummaryRepository(BaseRepository):
    def calendar_rows(self, start, end):
        rows = self.fetchall(
            "SELECT CAST(date AS TEXT) AS date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent "
            "FROM WorkCalendar WHERE date>=? AND date<=? ORDER BY date", (start, end))
        return {row["date"]: row for row in rows}
