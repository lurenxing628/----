"""Task feasibility facts do not redefine a resource's own calendar capacity."""

from collections import defaultdict

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_intervals import IntervalIndex, instant
from core.services.capacity.plan_calendar_windows import available_intervals
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.operator_qualification_repo import OperatorQualificationRepository

from .plan_calendar_context import issue
from .zero_duration import estimate_point_event


class _SkillFacts(OperatorQualificationRepository):
    """Connection-free read_skill_facts implementation for the domain service."""

    def __init__(self, facts):
        self.profiles = {row["operator_id"]: row for row in facts["skill_profiles"]}
        self.skills = defaultdict(list)
        for row in facts["skills"]:
            self.skills[row["operator_id"]].append(row)

    def read_skill_facts(self, operator_ids):
        return ([self.profiles[key] for key in operator_ids if key in self.profiles],
                [row for key in operator_ids for row in self.skills[key]])


class _Authorizations(OperatorMachineRepository):
    """Connection-free authorization lookup for the domain service."""

    def __init__(self, facts):
        self.links = {(row["operator_id"], row["machine_id"]) for row in facts["authorizations"]}

    def exists(self, operator_id, machine_id):
        return (operator_id, machine_id) in self.links


class TaskConstraints:
    def __init__(self, calendar_facts):
        self.available = calendar_facts["sources"] is not None
        self.resources = calendar_facts["resources"]
        self.issues = defaultdict(set)
        self.indexes, self.qualification_cache, self.skills_cache = {}, {}, {}
        if not self.available:
            return
        facts = calendar_facts["sources"]
        self.point_calendar = SnapshotCalendarEngine(facts)
        self.records = {kind: {row[kind + "_id"]: row for row in facts[kind + "s"]}
                        for kind in ("machine", "operator")}
        self.operations = {row["id"]: row for row in facts["operations"]}
        self.work_types = {row["op_type_id"]: row for row in facts["work_types"]}
        self.qualification = OperatorQualificationService(None)
        self.qualification.repo = _SkillFacts(facts)
        self.qualification.authorizations = _Authorizations(facts)
        self.downtime = defaultdict(list)
        for row in facts["downtimes"]:
            self.downtime[row["machine_id"]].append(row)

    def _add(self, code, op_id):
        self.issues[code].add(op_id)

    def check(self, row, start, end):
        op_id = row["op_id"]
        if not self.available:
            self._add("assignment_calendar_unavailable", op_id)
            return
        priority = str(row["priority"]).strip().lower() if row["priority"] is not None else None
        point = row.get("_point_work")
        if point:
            priority = point["batch"]["priority"]
            self._check_point_calendar(row, point, start)
        if priority not in ("normal", "urgent", "critical"):
            self._add("assignment_priority_unknown", op_id)
        for kind in ("machine", "operator"):
            key = row[kind + "_id"]
            if key in (None, ""):
                self._add("assignment_resource_missing", op_id)
                continue
            raw = self.records[kind].get(key)
            allowed = ("active", "inactive", "maintain") if kind == "machine" else ("active", "inactive")
            if raw is None or raw["status"] not in allowed:
                self._add("assignment_calendar_unavailable", op_id)
            elif raw["status"] != "active":
                self._add("assignment_resource_inactive", op_id)
            # CalendarEngine schedules with operator_id, not the global machine
            # capacity denominator. Night-shift personnel do not fail this check
            # merely because their machine's display calendar is a day shift.
            if not point and kind == "operator" and priority in ("normal", "urgent", "critical"):
                self._check_calendar(kind, key, priority, op_id, start, end)
        if not point:
            self._check_downtime(row, start, end)
        self._check_type_and_qualification(row)

    def _check_point_calendar(self, row, work, at):
        op, batch = work["operation"], work["batch"]
        try:
            start, end = estimate_point_event(self.point_calendar, setup_hours=op["setup_hours"],
                unit_hours=op["unit_hours"], quantity=batch["quantity"], priority=batch["priority"],
                machine_id=row["machine_id"], operator_id=row["operator_id"], start=at)
            if start != at or end != at:
                self._add("assignment_outside_calendar", row["op_id"])
        except (ValueError, TypeError, OverflowError):
            self._add("assignment_calendar_unavailable", row["op_id"])

    def _check_downtime(self, row, start, end):
        key = ("downtime", row["machine_id"])
        if key not in self.indexes:
            windows = []
            try:
                for item in self.downtime[row["machine_id"]]:
                    low, high = instant(item["start_time"]), instant(item["end_time"])
                    if low >= high or item["status"] != "active":
                        raise ValueError("Invalid downtime")
                    windows.append((low, high))
                self.indexes[key] = IntervalIndex(windows)
            except ValueError:
                self.indexes[key] = None
        index = self.indexes[key]
        if index is None:
            self._add("assignment_calendar_unavailable", row["op_id"])
        elif index.hours_between(start, end) > 1e-9:
            self._add("assignment_machine_downtime", row["op_id"])

    def _check_calendar(self, kind, key, priority, op_id, start, end):
        mode = "normal" if priority == "normal" else "urgent"
        cache_key = kind, key, mode
        if cache_key not in self.indexes:
            projection = self.resources[kind].get(key)
            windows = available_intervals(projection, mode) if projection is not None else None
            self.indexes[cache_key] = IntervalIndex(windows) if windows is not None else None
        index = self.indexes[cache_key]
        if index is None:
            self._add("assignment_calendar_unavailable", op_id)
        elif index.hours_between(start, end) + 1e-9 < (end - start).total_seconds() / 3600:
            self._add("assignment_outside_calendar", op_id)

    def _check_type_and_qualification(self, row):
        op_id, mid, oid = row["op_id"], row["machine_id"], row["operator_id"]
        operation, machine = self.operations.get(op_id), self.records["machine"].get(mid)
        code = operation["op_type_id"] if operation is not None else None
        work_type = self.work_types.get(code)
        if work_type is None or machine is None or machine["op_type_id"] is None:
            self._add("assignment_work_type_unknown", op_id)
        elif work_type["category"] != "internal" or machine["op_type_id"] != code:
            self._add("assignment_work_type_mismatch", op_id)
        if oid in (None, ""):
            return
        cache_key = oid, mid, code
        if cache_key not in self.qualification_cache:
            try:
                if oid not in self.skills_cache:
                    self.skills_cache[oid] = self.qualification.load([oid])
                self.qualification.require(operator_id=oid, op_type_id=code, machine_id=mid,
                                           qualifications=self.skills_cache[oid])
                failure = None
            except OperatorQualificationError as exc:
                reason = str((exc.details or {}).get("reason", ""))
                failure = {"operator_machine_not_authorized": "assignment_not_authorized",
                           "operator_skill_not_qualified": "assignment_not_qualified"}.get(
                               reason, "assignment_qualification_invalid")
            self.qualification_cache[cache_key] = failure
        if self.qualification_cache[cache_key] is not None:
            self._add(self.qualification_cache[cache_key], op_id)

    def public(self):
        return [issue(code, operation_count=len(ids)) for code, ids in sorted(self.issues.items())]

    def private(self):
        return {code: sorted(ids) for code, ids in sorted(self.issues.items())}
