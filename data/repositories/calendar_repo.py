from __future__ import annotations

from typing import Iterable, List, Optional

from core.models import WorkCalendar

from .base_repo import BaseRepository


class CalendarRepository(BaseRepository):
    """工作日历仓库（WorkCalendar）。"""

    def get(self, date: str) -> Optional[WorkCalendar]:
        row = self.fetchone(
            "SELECT date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json FROM WorkCalendar WHERE date = ?",
            (date,),
        )
        return WorkCalendar.from_row(row) if row else None

    def list_all(self) -> List[WorkCalendar]:
        rows = self.fetchall(
            "SELECT date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json FROM WorkCalendar ORDER BY date"
        )
        return [WorkCalendar.from_row(r) for r in rows]

    def list_range(self, start_date: str, end_date: str) -> List[WorkCalendar]:
        rows = self.fetchall(
            "SELECT date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        return [WorkCalendar.from_row(r) for r in rows]

    def upsert(self, calendar: WorkCalendar) -> WorkCalendar:
        self.upsert_many((calendar,))
        return calendar

    def upsert_many(self, calendars: Iterable[WorkCalendar]) -> None:
        self.executemany(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              day_type=excluded.day_type,
              shift_start=excluded.shift_start,
              shift_end=excluded.shift_end,
              shift_hours=excluded.shift_hours,
              efficiency=excluded.efficiency,
              allow_normal=excluded.allow_normal,
              allow_urgent=excluded.allow_urgent,
              remark=excluded.remark,
              periods_json=excluded.periods_json
            """,
            ((c.date, c.day_type, c.shift_start, c.shift_end, c.shift_hours, c.efficiency, c.allow_normal, c.allow_urgent, c.remark, c.periods_json) for c in calendars),
        )

    def delete_many(self, keys) -> None:
        self.executemany("DELETE FROM WorkCalendar WHERE date = ?", ((day,) for day in keys))

    def delete(self, date: str) -> None:
        self.execute("DELETE FROM WorkCalendar WHERE date = ?", (date,))

    def delete_all(self) -> None:
        self.execute("DELETE FROM WorkCalendar")

