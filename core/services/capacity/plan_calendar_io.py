"""Bounded snapshot-local reads; no per-resource/date SQL and no schema writes."""

import math
from collections import defaultdict
from typing import Optional

from data.repositories.calendar_facts_repo import CalendarFactsRepository
from data.repositories.schedule_time_sql import parse_dt_for_sql

MAX_FACT_ROWS = 50000
SQL_CHUNK = 400


class ProjectionLimit(ValueError):
    pass


class CapturedCalendarInputs:
    """Current dashboard source rows plus SQL-prepared downtime facts; no connection."""

    def __init__(self, *, machines, downtimes, schema_version, downtime_machine_ids):
        self.machine_rows, self.downtime_rows, self.schema_rows = machines, downtimes, schema_version
        # Downtimes were prepared only for these machines; other machines' calendars are unavailable.
        self.downtime_machine_ids = frozenset(downtime_machine_ids)
        self._machines, self._downtimes, self._downtime_order = None, None, {}
        self._version: Optional[int] = None

    def schema_version(self):
        if self._version is not None:
            return self._version
        value = next((row["version"] for row in self.schema_rows if row["id"] == 1), None)
        if type(value) is not int:
            raise ValueError("Calendar schema version is missing or invalid")
        self._version = value
        return value

    def _machine_rows(self, machine_ids, fields, limit):
        if self._machines is None:
            self._machines = defaultdict(list)
            for row in self.machine_rows:
                self._machines[row["machine_id"]].append(row)
        result = []
        for key in machine_ids:
            for row in self._machines.get(key, ()):
                result.append({field: row[field] for field in fields})
                if len(result) >= limit:
                    return result
        return result

    def machines(self, machine_ids, *, limit):
        return self._machine_rows(machine_ids, ("machine_id", "name", "status", "op_type_id"), limit)

    def machine_states(self, machine_ids, *, limit):
        return self._machine_rows(machine_ids, ("machine_id", "name", "status"), limit)

    def downtimes(self, machine_ids, end, start, *, limit):
        if not set(machine_ids) <= self.downtime_machine_ids:
            raise ProjectionLimit("calendar_unavailable")
        if self._downtimes is None:
            self._downtimes = defaultdict(list)
            for row, prepared in self.downtime_rows:
                if prepared["__calendar_admitted"] == 1:
                    self._downtimes[row["machine_id"]].append((row, prepared))
        low, high, result = parse_dt_for_sql(start), parse_dt_for_sql(end), []
        for key in machine_ids:
            if key not in self._downtime_order:
                self._downtime_order[key] = sorted(self._downtimes.get(key, ()), key=lambda item: (
                    item[1]["__calendar_start_time_rank"], item[1]["__calendar_start_time_value"],
                    item[1]["__calendar_end_time_rank"], item[1]["__calendar_end_time_value"]))
            for row, prepared in self._downtime_order[key]:
                overlaps = (prepared["__calendar_valid"] == 1 and low is not None and high is not None
                            and prepared["__calendar_start"] < high and prepared["__calendar_end"] > low)
                if overlaps or prepared["__calendar_valid"] == 0:
                    result.append({field: row[field] for field in ("machine_id", "start_time", "end_time", "status")})
                    if len(result) >= limit:
                        return result
        return result


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

    def __init__(self, conn, *, captured=None):
        self.repo = CalendarFactsRepository(conn)
        self.captured = captured
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
        if self.captured is not None:
            self.repo._read_schema_version = self.captured.schema_version()
        self.rows["legacy_defaults"] = self.repo.schema_version() < 34
        self.select("defaults", self.repo.defaults)
        self.select("global", self.repo.global_calendar, first, last)
        self.keyed("personal", self.repo.personal_calendar, operators, (first, last))
        self.keyed("profiles", self.repo.operator_profiles, operators)
        profile_ids = {row["profile_id"] for row in self.rows["profiles"] if row["profile_id"] is not None}
        self.keyed("patterns", self.repo.shift_patterns, profile_ids)

    def resources(self, machine_ids, operator_ids, operation_ids, start, end):
        self.keyed("machines", self.captured.machines if self.captured is not None else self.repo.machines, machine_ids)
        self.keyed("machine_capabilities", self.repo.machine_capabilities, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("operations", self.repo.operations, operation_ids)
        types = {row["op_type_id"] for name in ("machines", "operations", "machine_capabilities") for row in self.rows[name]
                 if row["op_type_id"] is not None}
        self.keyed("work_types", self.repo.work_types, types)
        self.keyed("authorizations", self.repo.authorizations, operator_ids)
        self.keyed("skill_profiles", self.repo.skill_profiles, operator_ids)
        self.keyed("skills", self.repo.skills, operator_ids)
        self.keyed("downtimes", self.captured.downtimes if self.captured is not None else self.repo.downtimes, machine_ids, (end, start))

    def resource_states(self, machine_ids, operator_ids, start, end):
        """Status-only machine/operator rows plus overlapping downtimes, for utilization calendars."""
        self.keyed("machines", self.captured.machine_states if self.captured is not None else self.repo.machine_states, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("downtimes", self.captured.downtimes if self.captured is not None else self.repo.downtimes, machine_ids, (end, start))
