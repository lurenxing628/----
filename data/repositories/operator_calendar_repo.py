from __future__ import annotations

from typing import Iterable, Optional

from core.models.calendar import OperatorCalendar

from .base_repo import BaseRepository


class OperatorCalendarRepository(BaseRepository):
    """人员专属工作日历仓库（OperatorCalendar）。"""

    def get(self, operator_id: str, date: str) -> Optional[OperatorCalendar]:
        row = self.fetchone(
            """
            SELECT operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json
            FROM OperatorCalendar
            WHERE operator_id = ? AND date = ?
            """,
            (operator_id, date),
        )
        return OperatorCalendar.from_row(row) if row else None

    def upsert_many(self, calendars: Iterable[OperatorCalendar]) -> None:
        self.executemany(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark, periods_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(operator_id, date) DO UPDATE SET
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
            ((c.operator_id, c.date, c.day_type, c.shift_start, c.shift_end, c.shift_hours, c.efficiency, c.allow_normal, c.allow_urgent, c.remark, c.periods_json) for c in calendars),
        )

    def delete_many(self, keys) -> None:
        self.executemany("DELETE FROM OperatorCalendar WHERE operator_id = ? AND date = ?", keys)

