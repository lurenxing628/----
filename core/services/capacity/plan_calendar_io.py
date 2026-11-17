"""Bounded snapshot-local reads; no per-resource/date SQL and no schema writes."""

from data.repositories.calendar_facts_repo import CalendarFactsRepository

MAX_FACT_ROWS = 50000


class ProjectionLimit(ValueError):
    pass


class CalendarFacts:
    """Named fact collections under one running row budget.

    Collections are read through the repository, or handed over as rows the caller's snapshot
    has already read (``captured``); both count against the same budget.
    """

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
        result = self._read(fetch, keys, *extra) if keys else []
        self.rows[name] = result
        return result

    def captured(self, name, rows):
        """Rows this snapshot already read for ``name``; they count against the budget like a repository read."""
        if len(rows) > MAX_FACT_ROWS - self.count:
            raise ProjectionLimit("calendar_fact_limit")
        self.count += len(rows)
        self.rows[name] = rows

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

    def assignments(self, machine_ids, operator_ids, operation_ids):
        """Work types, personnel and authorizations that task feasibility checks against."""
        self.keyed("machine_capabilities", self.repo.machine_capabilities, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("operations", self.repo.operations, operation_ids)
        # 设备能做的工种只在 MachineOpTypes；外协工序可以不带工种。
        types = {row["op_type_id"] for name in ("operations", "machine_capabilities") for row in self.rows[name]
                 if row["op_type_id"] is not None}
        self.keyed("work_types", self.repo.work_types, types)
        self.keyed("authorizations", self.repo.authorizations, operator_ids)
        self.keyed("skill_profiles", self.repo.skill_profiles, operator_ids)
        self.keyed("skills", self.repo.skills, operator_ids)

    def resources(self, machine_ids, operator_ids, operation_ids, start, end):
        self.keyed("machines", self.repo.machines, machine_ids)
        self.assignments(machine_ids, operator_ids, operation_ids)
        self.keyed("downtimes", self.repo.downtimes, machine_ids, (end, start))

    def resource_states(self, machine_ids, operator_ids, start, end):
        """Status-only machine/operator rows plus overlapping downtimes, for utilization calendars."""
        self.keyed("machines", self.repo.machines, machine_ids)
        self.keyed("operators", self.repo.operators, operator_ids)
        self.keyed("downtimes", self.repo.downtimes, machine_ids, (end, start))
