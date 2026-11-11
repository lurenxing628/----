"""Bounded snapshot-local reads; no per-resource/date SQL and no schema writes."""

from collections import defaultdict

from core.infrastructure.sqlite_udf import parse_dt_for_sql
from data.repositories.calendar_facts_repo import CalendarFactsRepository

MAX_FACT_ROWS = 50000
SQL_CHUNK = 400


class ProjectionLimit(ValueError):
    pass


# SQLite's ORDER BY across storage classes: NULL, then numbers, TEXT (binary collation), BLOB.
_STORAGE_CLASS_ORDER = {int: 1, float: 1, str: 2, bytes: 3}


def _sqlite_order(value):
    return (0, 0) if value is None else (_STORAGE_CLASS_ORDER[type(value)], value)


class CapturedCalendarInputs:
    """Current dashboard source rows plus SQL-prepared downtime facts; no connection.

    ``downtimes`` arrive in rowid order and keep each machine's rowid capture order,
    matching CalendarFactsRepository.downtimes' ORDER BY md.machine_id,md.rowid;
    CalendarFacts.read_downtimes stably sorts admitted rows by (start_time, end_time).
    """

    def __init__(self, *, machines, downtimes, schema_version, downtime_machine_ids):
        # schema_rows 只作日历来源说明（source.schema_version）原样带出，不参与日历计算。
        self.machine_rows, self.downtime_rows, self.schema_rows = machines, downtimes, schema_version
        # Downtimes were prepared only for these machines; other machines' calendars are unavailable.
        self.downtime_machine_ids = frozenset(downtime_machine_ids)
        self._machines, self._downtimes = None, None

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
                # Only the selected machines' admitted rows were prepared (valid is 0 or 1).
                if prepared["__calendar_valid"] is not None:
                    self._downtimes[row["machine_id"]].append((row, prepared))
        low, high, result = parse_dt_for_sql(start), parse_dt_for_sql(end), []
        for key in machine_ids:
            for row, prepared in self._downtimes.get(key, ()):
                overlaps = (prepared["__calendar_valid"] == 1 and low is not None and high is not None
                            and prepared["__calendar_start"] < high and prepared["__calendar_end"] > low)
                if overlaps or prepared["__calendar_valid"] == 0:
                    result.append({field: row[field] for field in ("machine_id", "start_time", "end_time", "status")})
                    if len(result) >= limit:
                        return result
        return result


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

    def read_downtimes(self, machine_ids, start, end):
        rows = self.keyed(
            "downtimes",
            self.captured.downtimes if self.captured is not None else self.repo.downtimes,
            machine_ids,
            (end, start),
        )
        rows.sort(
            key=lambda row: (row["machine_id"], _sqlite_order(row["start_time"]), _sqlite_order(row["end_time"]))
        )
        return rows

    def calendar(self, first, last, operators):
        self.select("defaults", self.repo.defaults)
        self.select("global", self.repo.global_calendar, first, last)
        self.keyed("personal", self.repo.personal_calendar, operators, (first, last))
        self.keyed("profiles", self.repo.operator_profiles, operators)
        shift_profiles = {}
        for row in self.rows["profiles"]:
            profile_id = row["profile_id"]
            if profile_id is not None and profile_id not in shift_profiles:
                shift_profiles[profile_id] = {
                    "profile_id": profile_id,
                    "anchor_date": row["anchor_date"],
                    "cycle_days": row["cycle_days"],
                    "status": row["status"],
                }
        self.rows["shift_profiles"] = list(shift_profiles.values())
        self.keyed("patterns", self.repo.shift_patterns, shift_profiles)

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
        self.read_downtimes(machine_ids, start, end)

    def resource_states(self, machine_ids, operator_ids, start, end):
        """Status-only machine/operator rows plus overlapping downtimes, for utilization calendars."""
        self.keyed("machines", self.captured.machine_states if self.captured is not None else self.repo.machine_states, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.read_downtimes(machine_ids, start, end)
