from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import WorkCalendar

from .base_repo import BaseRepository


class CalendarRepository(BaseRepository):
    """工作日历仓库（WorkCalendar）。"""

    def get(self, date: str) -> Optional[WorkCalendar]:
        row = self.fetchone(
            "SELECT date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark FROM WorkCalendar WHERE date = ?",
            (date,),
        )
        return WorkCalendar.from_row(row) if row else None

    def list_all(self) -> List[WorkCalendar]:
        rows = self.fetchall(
            "SELECT date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark FROM WorkCalendar ORDER BY date"
        )
        return [WorkCalendar.from_row(r) for r in rows]

    def list_range(self, start_date: str, end_date: str) -> List[WorkCalendar]:
        rows = self.fetchall(
            "SELECT date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        return [WorkCalendar.from_row(r) for r in rows]

    def upsert(self, calendar: Union[WorkCalendar, Dict[str, Any]]) -> WorkCalendar:
        c = calendar if isinstance(calendar, WorkCalendar) else WorkCalendar.from_row(calendar)
        self.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              day_type=excluded.day_type,
              shift_hours=excluded.shift_hours,
              efficiency=excluded.efficiency,
              allow_normal=excluded.allow_normal,
              allow_urgent=excluded.allow_urgent,
              remark=excluded.remark
            """,
            (c.date, c.day_type, c.shift_hours, c.efficiency, c.allow_normal, c.allow_urgent, c.remark),
        )
        return c

    def delete(self, date: str) -> None:
        self.execute("DELETE FROM WorkCalendar WHERE date = ?", (date,))

