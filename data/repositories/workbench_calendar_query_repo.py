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
        return self.fetchall(
            "SELECT * FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date", (start_date, end_date))

    def identity_rows(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """All calendar refs in the range, including tombstones (absent -> created -> deleted ABA)."""
        return self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs "
            "WHERE kind = 'calendar' AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key, ref",
            (start_date, end_date),
        )

    def operator_calendar_rows(self, operator_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """某个人在这段日期里的个人日历原始行；与上面的全局读取同一条事务由调用方持有。"""
        return self.fetchall(
            "SELECT * FROM OperatorCalendar WHERE operator_id = ? AND date >= ? AND date <= ? ORDER BY date",
            (operator_id, start_date, end_date))

    def operator_identity_rows(self, operator_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """个人日历的身份记录含墓碑。复合键是"工号:日期"，工号一致时按日期排序等价于按键排序。"""
        from core.infrastructure.workbench_metadata_schema import entity_key

        low, high = entity_key(operator_id, start_date), entity_key(operator_id, end_date)
        return self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs "
            "WHERE kind = 'operator_calendar' AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key, ref",
            (low, high),
        )

    def operator_calendar_rows_many(self, operator_ids, start_date, end_date):
        codes = list(dict.fromkeys(operator_ids))
        result = {code: [] for code in codes}
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT * FROM OperatorCalendar WHERE operator_id IN (" + marks + ") "
                                     "AND date >= ? AND date <= ? ORDER BY operator_id,date",
                                     chunk + [start_date, end_date]):
                result[row["operator_id"]].append(row)
        return result

    def operator_identity_rows_many(self, operator_ids, start_date, end_date):
        """Keep each encoded operator's exact range, including all retired references."""
        from core.infrastructure.workbench_metadata_schema import entity_key

        codes = list(dict.fromkeys(operator_ids))
        result = {code: [] for code in codes}
        prefixes = {entity_key(code, "")[:-1]: code for code in codes}
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            ranges = " OR ".join("(entity_key >= ? AND entity_key <= ?)" for _ in chunk)
            params = [value for code in chunk for value in (entity_key(code, start_date), entity_key(code, end_date))]
            for row in self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                                     "WHERE kind='operator_calendar' AND (" + ranges + ") ORDER BY entity_key,ref", params):
                result[prefixes[row["entity_key"].split(":", 1)[0]]].append(row)
        return result

    def created_refs(self, kind: str, keys) -> Dict[str, str]:
        result = {}
        keys = list(keys)
        for offset in range(0, len(keys), 500):
            chunk = keys[offset:offset + 500]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall(
                    "SELECT entity_key, ref FROM WorkbenchEntityRefs WHERE kind = ? AND active = 1 "
                    "AND entity_key IN (" + marks + ")", [kind] + chunk):
                result[row["entity_key"]] = row["ref"]
        return result
