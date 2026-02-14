from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import OperatorCalendar

from .base_repo import BaseRepository


class OperatorCalendarRepository(BaseRepository):
    """人员专属工作日历仓库（OperatorCalendar）。"""

    def get(self, operator_id: str, date: str) -> Optional[OperatorCalendar]:
        row = self.fetchone(
            """
            SELECT operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark
            FROM OperatorCalendar
            WHERE operator_id = ? AND date = ?
            """,
            (operator_id, date),
        )
        return OperatorCalendar.from_row(row) if row else None

    def list_by_operator(self, operator_id: str) -> List[OperatorCalendar]:
        rows = self.fetchall(
            """
            SELECT operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark
            FROM OperatorCalendar
            WHERE operator_id = ?
            ORDER BY date
            """,
            (operator_id,),
        )
        return [OperatorCalendar.from_row(r) for r in rows]

    def list_all(self) -> List[OperatorCalendar]:
        rows = self.fetchall(
            """
            SELECT operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark
            FROM OperatorCalendar
            ORDER BY operator_id, date
            """
        )
        return [OperatorCalendar.from_row(r) for r in rows]

    def upsert(self, calendar: Union[OperatorCalendar, Dict[str, Any]]) -> OperatorCalendar:
        c = calendar if isinstance(calendar, OperatorCalendar) else OperatorCalendar.from_row(calendar)
        self.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(operator_id, date) DO UPDATE SET
              day_type=excluded.day_type,
              shift_start=excluded.shift_start,
              shift_end=excluded.shift_end,
              shift_hours=excluded.shift_hours,
              efficiency=excluded.efficiency,
              allow_normal=excluded.allow_normal,
              allow_urgent=excluded.allow_urgent,
              remark=excluded.remark
            """,
            (
                c.operator_id,
                c.date,
                c.day_type,
                c.shift_start,
                c.shift_end,
                c.shift_hours,
                c.efficiency,
                c.allow_normal,
                c.allow_urgent,
                c.remark,
            ),
        )
        return c

    def delete(self, operator_id: str, date: str) -> None:
        self.execute("DELETE FROM OperatorCalendar WHERE operator_id = ? AND date = ?", (operator_id, date))

    def delete_all(self) -> None:
        self.execute("DELETE FROM OperatorCalendar")

