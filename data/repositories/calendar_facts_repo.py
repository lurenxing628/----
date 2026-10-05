"""Bounded snapshot-local calendar and resource fact reads for plan calendar projections.

Every method appends the caller's row limit; the caller keeps the running fact
count, decides when a projection is over budget, and chunks keyed lookups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .base_repo import BaseRepository
from .schedule_time_sql import overlap_or_bad_time_sql, register_schedule_time_sql_functions

_DOWNTIMES_SQL = ("SELECT machine_id,start_time,end_time,status FROM MachineDowntimes md "
                  "WHERE machine_id IN ({marks}) AND (status='active' OR status IS NULL OR status NOT IN ('active','cancelled')) "
                  "AND " + overlap_or_bad_time_sql("md") + " ORDER BY machine_id,start_time,end_time")


class CalendarFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def schema_version(self):
        if not hasattr(self, "_read_schema_version"):
            self._read_schema_version = self.fetchvalue("SELECT version FROM SchemaVersion WHERE id=1")
            if type(self._read_schema_version) is not int:
                raise ValueError("Calendar schema version is missing or invalid")
        return self._read_schema_version

    def _bounded(self, sql: str, params: Sequence[Any], limit: int) -> List[Dict[str, Any]]:
        return self.fetchall(sql + " LIMIT ?", list(params) + [limit])

    def _keyed(self, sql: str, keys: Sequence[Any], extra: Sequence[Any], limit: int) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in keys)
        return self._bounded(sql.format(marks=marks), list(keys) + list(extra), limit)

    def defaults(self, *, limit: int) -> List[Dict[str, Any]]:
        if self.schema_version() < 34:
            return []
        return self._bounded("SELECT * FROM WorkbenchCalendarDefaults ORDER BY singleton", (), limit)

    def global_calendar(self, first: str, last: str, *, limit: int) -> List[Dict[str, Any]]:
        return self._bounded("SELECT * FROM WorkCalendar WHERE date>=? AND date<=? ORDER BY date", (first, last), limit)

    def personal_calendar(self, operator_ids: Sequence[str], first: str, last: str, *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT * FROM OperatorCalendar WHERE operator_id IN ({marks}) "
                           "AND date>=? AND date<=? ORDER BY operator_id,date", operator_ids, (first, last), limit)

    def operator_profiles(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT p.operator_id,p.shift_profile_id,s.profile_id,s.anchor_date,s.cycle_days,s.status "
                           "FROM WorkbenchOperatorProfiles p LEFT JOIN WorkbenchShiftProfiles s ON s.profile_id=p.shift_profile_id "
                           "WHERE p.operator_id IN ({marks}) AND p.shift_profile_id IS NOT NULL ORDER BY p.operator_id",
                           operator_ids, (), limit)

    def shift_patterns(self, profile_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        if self.schema_version() < 34:
            return self._keyed("SELECT d.*,NULL AS periods_json FROM WorkbenchShiftPatternDays d WHERE d.profile_id IN ({marks}) ORDER BY d.profile_id,d.day_offset", profile_ids, (), limit)
        return self._keyed("SELECT d.*,p.periods_json FROM WorkbenchShiftPatternDays d LEFT JOIN WorkbenchShiftDayPeriods p "
                           "ON p.profile_id=d.profile_id AND p.day_offset=d.day_offset WHERE d.profile_id IN ({marks}) "
                           "ORDER BY d.profile_id,d.day_offset", profile_ids, (), limit)

    def machines(self, machine_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT machine_id,name,status,op_type_id FROM Machines "
                           "WHERE machine_id IN ({marks}) ORDER BY machine_id", machine_ids, (), limit)

    def machine_capabilities(self, machine_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        if self.schema_version() < 35:
            return []
        return self._keyed("SELECT machine_id,op_type_id FROM MachineOpTypes WHERE machine_id IN ({marks}) "
                           "ORDER BY machine_id,op_type_id", machine_ids, (), limit)

    def machine_states(self, machine_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT machine_id,name,status FROM Machines WHERE machine_id IN ({marks}) ORDER BY machine_id",
                           machine_ids, (), limit)

    def operators(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT operator_id,name,status FROM Operators "
                           "WHERE operator_id IN ({marks}) ORDER BY operator_id", operator_ids, (), limit)

    def operations(self, operation_ids: Sequence[int], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT id,op_type_id FROM BatchOperations WHERE id IN ({marks}) ORDER BY id",
                           operation_ids, (), limit)

    def work_types(self, op_type_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT op_type_id,name,category FROM OpTypes "
                           "WHERE op_type_id IN ({marks}) ORDER BY op_type_id", op_type_ids, (), limit)

    def authorizations(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT operator_id,machine_id FROM OperatorMachine "
                           "WHERE operator_id IN ({marks}) ORDER BY operator_id,machine_id", operator_ids, (), limit)

    def skill_profiles(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT o.operator_id,p.operator_id AS profile_operator_id,p.skills_declared "
                           "FROM Operators o LEFT JOIN WorkbenchOperatorProfiles p ON p.operator_id=o.operator_id "
                           "WHERE o.operator_id IN ({marks}) ORDER BY o.operator_id", operator_ids, (), limit)

    def skills(self, operator_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        return self._keyed("SELECT s.operator_id,s.op_type_id,t.category FROM OperatorSkill s "
                           "LEFT JOIN OpTypes t ON t.op_type_id=s.op_type_id WHERE s.operator_id IN ({marks}) "
                           "ORDER BY s.operator_id,s.op_type_id", operator_ids, (), limit)

    def downtimes(self, machine_ids: Sequence[str], end: Any, start: Any, *, limit: int) -> List[Dict[str, Any]]:
        """Active or bad-time downtimes overlapping [start, end); bound order is (end, start)."""
        return self._keyed(_DOWNTIMES_SQL, machine_ids, (end, start), limit)
