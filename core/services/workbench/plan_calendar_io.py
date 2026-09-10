"""Bounded snapshot-local reads; no per-resource/date SQL and no schema writes."""

import math

from data.repositories.base_repo import BaseRepository
from data.repositories.schedule_time_sql import overlap_or_bad_time_sql

MAX_FACT_ROWS = 50000
SQL_CHUNK = 400


class ProjectionLimit(ValueError):
    pass


def snapshot_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"invalid_number": repr(value)}
    if isinstance(value, dict):
        return {key: snapshot_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [snapshot_values(item) for item in value]
    return value


class CalendarFacts:
    def __init__(self, conn):
        self.repo = BaseRepository(conn)
        self.rows = {}
        self.count = 0

    def _read(self, sql, params):
        remaining = MAX_FACT_ROWS - self.count
        rows = self.repo.fetchall(sql + " LIMIT ?", list(params) + [remaining + 1])
        if len(rows) > remaining:
            raise ProjectionLimit("calendar_fact_limit")
        self.count += len(rows)
        return rows

    def select(self, name, sql, params=()):
        self.rows[name] = self._read(sql, params)
        return self.rows[name]

    def keyed(self, name, sql, keys, extra=()):
        result = []
        keys = sorted(set(keys))
        for offset in range(0, len(keys), SQL_CHUNK):
            chunk = keys[offset:offset + SQL_CHUNK]
            marks = ",".join("?" for _ in chunk)
            result.extend(self._read(sql.format(marks=marks), list(chunk) + list(extra)))
        self.rows[name] = result
        return result

    def calendar(self, first, last, operators):
        self.select("global", "SELECT * FROM WorkCalendar WHERE date>=? AND date<=? ORDER BY date", (first, last))
        self.keyed("personal", "SELECT * FROM OperatorCalendar WHERE operator_id IN ({marks}) "
                   "AND date>=? AND date<=? ORDER BY operator_id,date", operators, (first, last))
        self.keyed("profiles", "SELECT p.operator_id,p.shift_profile_id,s.profile_id,s.anchor_date,s.cycle_days,s.status "
                   "FROM WorkbenchOperatorProfiles p LEFT JOIN WorkbenchShiftProfiles s ON s.profile_id=p.shift_profile_id "
                   "WHERE p.operator_id IN ({marks}) AND p.shift_profile_id IS NOT NULL ORDER BY p.operator_id", operators)
        profile_ids = {row["profile_id"] for row in self.rows["profiles"] if row["profile_id"] is not None}
        self.keyed("patterns", "SELECT * FROM WorkbenchShiftPatternDays WHERE profile_id IN ({marks}) "
                   "ORDER BY profile_id,day_offset", profile_ids)

    def resources(self, machine_ids, operator_ids, operation_ids, start, end):
        self.keyed("machines", "SELECT machine_id,name,status,op_type_id FROM Machines "
                   "WHERE machine_id IN ({marks}) ORDER BY machine_id", machine_ids)
        self.keyed("operators", "SELECT operator_id,name,status FROM Operators "
                   "WHERE operator_id IN ({marks}) ORDER BY operator_id", operator_ids)
        self.keyed("operations", "SELECT id,op_type_id FROM BatchOperations WHERE id IN ({marks}) ORDER BY id", operation_ids)
        types = {row["op_type_id"] for name in ("machines", "operations") for row in self.rows[name]
                 if row["op_type_id"] is not None}
        self.keyed("work_types", "SELECT op_type_id,name,category FROM OpTypes "
                   "WHERE op_type_id IN ({marks}) ORDER BY op_type_id", types)
        self.keyed("authorizations", "SELECT operator_id,machine_id FROM OperatorMachine "
                   "WHERE operator_id IN ({marks}) ORDER BY operator_id,machine_id", operator_ids)
        self.keyed("skill_profiles", "SELECT o.operator_id,p.operator_id AS profile_operator_id,p.skills_declared "
                   "FROM Operators o LEFT JOIN WorkbenchOperatorProfiles p ON p.operator_id=o.operator_id "
                   "WHERE o.operator_id IN ({marks}) ORDER BY o.operator_id", operator_ids)
        self.keyed("skills", "SELECT s.operator_id,s.op_type_id,t.category FROM OperatorSkill s "
                   "LEFT JOIN OpTypes t ON t.op_type_id=s.op_type_id WHERE s.operator_id IN ({marks}) "
                   "ORDER BY s.operator_id,s.op_type_id", operator_ids)
        self.keyed("downtimes", "SELECT machine_id,start_time,end_time,status FROM MachineDowntimes md "
                   "WHERE machine_id IN ({marks}) AND (status='active' OR status IS NULL OR status NOT IN ('active','cancelled')) "
                   "AND " + overlap_or_bad_time_sql("md") + " ORDER BY machine_id,start_time,end_time",
                   machine_ids, (end, start))
