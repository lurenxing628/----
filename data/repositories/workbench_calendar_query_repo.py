"""Read raw global calendar rows and lifetime references without repairing metadata or ruling on them."""

from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository


class WorkbenchCalendarQueryRepository(BaseRepository):
    def calendar_rows(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Private SQL projection; caller owns one read/write transaction for both reads.

        SELECT * intentionally keeps all raw columns for snapshot comparison and
        omission preservation. The stored date is returned as SQLite delivers it
        (get_connection enables DATE conversion); the service decides whether it is a valid date key.
        """
        return [dict(raw) for raw in self.fetchall(
            "SELECT * FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date", (start_date, end_date))]

    def identity_rows(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """All calendar refs in the range, including tombstones (absent -> created -> deleted ABA)."""
        return [dict(row) for row in self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs "
            "WHERE kind = 'calendar' AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key, ref",
            (start_date, end_date),
        )]

    def operator_calendar_rows(self, operator_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """某个人在这段日期里的个人日历原始行；与上面的全局读取同一条事务由调用方持有。"""
        return [dict(raw) for raw in self.fetchall(
            "SELECT * FROM OperatorCalendar WHERE operator_id = ? AND date >= ? AND date <= ? ORDER BY date",
            (operator_id, start_date, end_date))]

    def operator_identity_rows(self, operator_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """个人日历的身份记录含墓碑。复合键是"工号:日期"，工号一致时按日期排序等价于按键排序。"""
        from core.infrastructure.workbench_metadata_schema import entity_key

        low, high = entity_key(operator_id, start_date), entity_key(operator_id, end_date)
        return [dict(row) for row in self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs "
            "WHERE kind = 'operator_calendar' AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key, ref",
            (low, high),
        )]
