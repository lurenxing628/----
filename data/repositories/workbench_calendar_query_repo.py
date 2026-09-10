"""Read raw global calendar rows and lifetime references without repairing metadata."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from core.errors import ValidationError
from core.models.workbench_calendar import calendar_date
from core.models.workbench_command import WorkbenchCommandRejected

from .base_repo import BaseRepository


def _date_key(value: Any) -> str:
    # get_connection enables SQLite DATE conversion. datetime is deliberately not a date key.
    if type(value) is date:
        return value.isoformat()
    try:
        return calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储日历的日期无效，不能当作本地日期读取。") from exc


class WorkbenchCalendarQueryRepository(BaseRepository):
    def range_states(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Private SQL projection; caller owns one read/write transaction for both reads.

        SELECT * intentionally keeps all raw columns for snapshot comparison and
        omission preservation. Tombstones detect absent -> created -> deleted ABA.
        An absent date has row=None and identity=None; a GET never invents a ref.
        """
        rows = {}
        for raw in self.fetchall("SELECT * FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date", (start_date, end_date)):
            row = dict(raw)
            row["date"] = _date_key(row["date"])
            rows[row["date"]] = row
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for row in self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs "
            "WHERE kind = 'calendar' AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key, ref",
            (start_date, end_date),
        ):
            identity = dict(row)
            identity["entity_key"] = _date_key(identity["entity_key"])
            histories.setdefault(identity["entity_key"], []).append(identity)
        result = {}
        for day in sorted(rows.keys() | histories.keys()):
            row, history = rows.get(day), histories.get(day, [])
            active = [item for item in history if item["active"] == 1]
            if len(active) != (1 if row is not None else 0):
                raise WorkbenchCommandRejected("constraint_conflict", "日历与永久引用不一致，请检查数据后重试。")
            result[day] = {"row": row, "identity": active[0] if active else None, "history": history}
        return result
