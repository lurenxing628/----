"""Bounded snapshot-local calendar and resource fact reads for plan calendar projections.

Every method appends the caller's row limit; the caller keeps the running fact
count and decides when a projection is over budget.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Sequence

from core.shared.local_datetime import datetime_to_us

from .base_repo import BaseRepository

# 走 (machine_id, start_us, end_us) 复合索引；已取消的不是停机。
_DOWNTIMES_SQL = (
    "SELECT machine_id,start_us,end_us,status FROM MachineDowntimes "
    "WHERE machine_id IN (SELECT value FROM json_each(?)) AND status='active' AND start_us<? AND end_us>? "
    "ORDER BY machine_id,start_us,end_us"
)


class CalendarFactsRepository(BaseRepository):
    def _bounded(self, sql: str, params: Sequence[Any], limit: int) -> List[Dict[str, Any]]:
        return self.fetchall(sql + " LIMIT ?", list(params) + [limit])

    def _keyed(self, sql: str, keys: Sequence[Any], extra: Sequence[Any], limit: int) -> List[Dict[str, Any]]:
        return self._bounded(sql, [json.dumps(list(keys)), *extra], limit)

    def defaults(self, *, limit: int) -> List[Dict[str, Any]]:
        return self._bounded("SELECT * FROM WorkbenchCalendarDefaults ORDER BY singleton", (), limit)

    def global_calendar(self, first: str, last: str, *, limit: int) -> List[Dict[str, Any]]:
        return self._bounded("SELECT * FROM WorkCalendar WHERE date>=? AND date<=? ORDER BY date", (first, last), limit)

    def personal_calendar(self, operator_ids: Sequence[str], first: str, last: str, *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT * FROM OperatorCalendar WHERE operator_id IN (SELECT value FROM json_each(?)) "
                           "AND date>=? AND date<=? ORDER BY operator_id,date", operator_ids, (first, last), limit)

    def operator_profiles(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT p.operator_id,p.shift_profile_id,s.profile_id,s.anchor_date,s.cycle_days,s.status "
                           "FROM WorkbenchOperatorProfiles p LEFT JOIN WorkbenchShiftProfiles s ON s.profile_id=p.shift_profile_id "
                           "WHERE p.operator_id IN (SELECT value FROM json_each(?)) AND p.shift_profile_id IS NOT NULL ORDER BY p.operator_id",
                           operator_ids, (), limit)

    def shift_patterns(self, profile_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT * FROM WorkbenchShiftPatternDays WHERE profile_id IN (SELECT value FROM json_each(?)) "
                           "ORDER BY profile_id,day_offset", profile_ids, (), limit)

    def machines(self, machine_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT machine_id,name,status FROM Machines "
                           "WHERE machine_id IN (SELECT value FROM json_each(?)) ORDER BY machine_id", machine_ids, (), limit)

    def machine_capabilities(self, machine_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT machine_id,op_type_id FROM MachineOpTypes WHERE machine_id IN (SELECT value FROM json_each(?)) "
                           "ORDER BY machine_id,op_type_id", machine_ids, (), limit)

    def operators(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT operator_id,name,status FROM Operators "
                           "WHERE operator_id IN (SELECT value FROM json_each(?)) ORDER BY operator_id", operator_ids, (), limit)

    def operations(self, operation_ids: Sequence[int], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT id,op_type_id FROM BatchOperations WHERE id IN (SELECT value FROM json_each(?)) ORDER BY id",
                           operation_ids, (), limit)

    def work_types(self, op_type_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT op_type_id,name,category FROM OpTypes "
                           "WHERE op_type_id IN (SELECT value FROM json_each(?)) ORDER BY op_type_id", op_type_ids, (), limit)

    def authorizations(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT operator_id,machine_id FROM OperatorMachine "
                           "WHERE operator_id IN (SELECT value FROM json_each(?)) ORDER BY operator_id,machine_id", operator_ids, (), limit)

    def skill_profiles(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT o.operator_id,p.operator_id AS profile_operator_id,p.skills_declared "
                           "FROM Operators o LEFT JOIN WorkbenchOperatorProfiles p ON p.operator_id=o.operator_id "
                           "WHERE o.operator_id IN (SELECT value FROM json_each(?)) ORDER BY o.operator_id", operator_ids, (), limit)

    def skills(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT s.operator_id,s.op_type_id,t.category FROM OperatorSkill s "
                           "LEFT JOIN OpTypes t ON t.op_type_id=s.op_type_id WHERE s.operator_id IN (SELECT value FROM json_each(?)) "
                           "ORDER BY s.operator_id,s.op_type_id", operator_ids, (), limit)

    def downtimes(self, machine_ids: Sequence[str], end: datetime, start: datetime, *, limit: int) -> List[Dict[str, Any]]:
        """Active downtimes overlapping [start, end), ordered by (machine_id, start_us, end_us); bound order is (end, start)."""
        return self._keyed(_DOWNTIMES_SQL, machine_ids, (datetime_to_us(end), datetime_to_us(start)), limit)
