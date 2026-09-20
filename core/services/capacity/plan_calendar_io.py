"""Bounded snapshot-local reads; no per-resource/date SQL and no schema writes."""

import math

from data.repositories.calendar_facts_repo import CalendarFactsRepository

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
    """Named fact collections read through the repository under one running row budget."""

    def __init__(self, conn):
        self.repo = CalendarFactsRepository(conn)
        self.rows = {}
        self.count = 0

    def _read(self, fetch, *params):
        remaining = MAX_FACT_ROWS - self.count
        rows = fetch(*params, limit=remaining + 1)
        if len(rows) > remaining:
            raise ProjectionLimit("calendar_fact_limit")
        self.count += len(rows)
        return rows

    def select(self, name, fetch, *params):
        self.rows[name] = self._read(fetch, *params)
        return self.rows[name]

    def keyed(self, name, fetch, keys, extra=()):
        result = []
        keys = sorted(set(keys))
        for offset in range(0, len(keys), SQL_CHUNK):
            chunk = keys[offset:offset + SQL_CHUNK]
            result.extend(self._read(fetch, chunk, *extra))
        self.rows[name] = result
        return result

    def calendar(self, first, last, operators):
        self.select("global", self.repo.global_calendar, first, last)
        self.keyed("personal", self.repo.personal_calendar, operators, (first, last))
        self.keyed("profiles", self.repo.operator_profiles, operators)
        profile_ids = {row["profile_id"] for row in self.rows["profiles"] if row["profile_id"] is not None}
        self.keyed("patterns", self.repo.shift_patterns, profile_ids)

    def resources(self, machine_ids, operator_ids, operation_ids, start, end):
        self.keyed("machines", self.repo.machines, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("operations", self.repo.operations, operation_ids)
        types = {row["op_type_id"] for name in ("machines", "operations") for row in self.rows[name]
                 if row["op_type_id"] is not None}
        self.keyed("work_types", self.repo.work_types, types)
        self.keyed("authorizations", self.repo.authorizations, operator_ids)
        self.keyed("skill_profiles", self.repo.skill_profiles, operator_ids)
        self.keyed("skills", self.repo.skills, operator_ids)
        self.keyed("downtimes", self.repo.downtimes, machine_ids, (end, start))

    def resource_states(self, machine_ids, operator_ids, start, end):
        """Status-only machine/operator rows plus overlapping downtimes, for utilization calendars."""
        self.keyed("machines", self.repo.machine_states, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("downtimes", self.repo.downtimes, machine_ids, (end, start))
