"""Saved calendar facts projected through the existing factory-local rules.

Run and trial captures contain whole business tables. A caller with a bounded
calendar archive declares its evaluable ``coverage`` instead. Nothing is read
from a connection or filled from a current resource/calendar directory.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_intervals import instant, union
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES
from core.services.capacity.plan_calendar_windows import apply_resource, policy_projection, unavailable

from .candidate_facts import archived_table
from .candidate_values import corrupt

_MEASURES = ("available_hours", "effective_hours", "normal_available_hours", "normal_effective_hours",
             "urgent_available_hours", "urgent_effective_hours")


class _SavedCalendarEngine(SnapshotCalendarEngine):
    """Resolve absent saved tables at the policy that actually needs them.

    A table missing from the saved snapshot only fails the dates and people whose
    policy reads it (recorded in missing_policies); damaged calendar content is
    deferred the same way by SnapshotCalendarEngine. All policy, shift and interval
    math remain in the shared engine.
    """

    def __init__(self, tables, version):
        self.tables, self.version = tables, version
        self.missing_policies = {}
        profiles = {row["profile_id"]: row for row in tables["WorkbenchShiftProfiles"] or []}
        self.members = {row["operator_id"]: row for row in tables["WorkbenchOperatorProfiles"] or []}
        selected = [{"operator_id": row["operator_id"], "shift_profile_id": row["shift_profile_id"],
                     **profiles.get(row["shift_profile_id"], {"profile_id": None, "status": None,
                                                            "anchor_date": None, "cycle_days": None})}
                    for row in self.members.values() if row.get("shift_profile_id") is not None]
        periods = {(row["profile_id"], row["day_offset"]): row["periods_json"]
                   for row in tables["WorkbenchShiftDayPeriods"] or []} if version is not None and version >= 34 else {}
        patterns = [dict(row, periods_json=periods.get((row["profile_id"], row["day_offset"])))
                    for row in tables["WorkbenchShiftPatternDays"] or []]
        super().__init__({"global": tables["WorkCalendar"] or [], "personal": tables["OperatorCalendar"] or [],
                          "profiles": selected, "patterns": patterns,
                          "defaults": tables["WorkbenchCalendarDefaults"] or [],
                          "legacy_defaults": version is not None and version < 34})

    def _missing(self, name, day, operator_id=None):
        self.missing_policies[(operator_id, day)] = name
        raise ValidationError("保存的日历资料缺少 " + name + "。", field=name)

    def _resolve_calendar_row(self, date_str, op_id):
        if op_id is not None:
            if self.tables["OperatorCalendar"] is None:
                self._missing("OperatorCalendar", date_str, op_id)
            # 个人日历表坏了时查不清这天有没有个人日历，先于班表资料报个人日历无效。
            if self._personal_error is not None or (op_id, date_str) in self.personal_rows:
                return super()._resolve_calendar_row(date_str, op_id)
            if self.tables["WorkbenchOperatorProfiles"] is None:
                self._missing("WorkbenchOperatorProfiles", date_str, op_id)
            member = self.members.get(op_id)
            if member is not None and member.get("shift_profile_id") is not None:
                for name in ("WorkbenchShiftProfiles", "WorkbenchShiftPatternDays"):
                    if self.tables[name] is None:
                        self._missing(name, date_str, op_id)
                if self.version is None:
                    self._missing("SchemaVersion", date_str, op_id)
                if self.version >= 34 and self.tables["WorkbenchShiftDayPeriods"] is None:
                    self._missing("WorkbenchShiftDayPeriods", date_str, op_id)
        if self.tables["WorkCalendar"] is None:
            self._missing("WorkCalendar", date_str, op_id)
        return super()._resolve_calendar_row(date_str, op_id)

    def _default_for_date(self, date_str):
        if self.version is None:
            self._missing("SchemaVersion", date_str)
        if self.version >= 34 and date.fromisoformat(date_str).weekday() < 5 and self.tables["WorkbenchCalendarDefaults"] is None:
            self._missing("WorkbenchCalendarDefaults", date_str)
        return super()._default_for_date(date_str)


def _bounds(start, end):
    low, high = instant(start), instant(end)
    if low > high:
        raise WorkbenchCommandRejected("invalid_input", "资源比较窗口的结束不能早于开始。", 422)
    last = (high - timedelta(microseconds=1)).date() if low < high else low.date()
    if (last - low.date()).days + 1 > MAX_CALENDAR_DATES:
        raise WorkbenchCommandRejected("invalid_input", "资源比较窗口超过 3660 天，请缩小时间范围。", 422)
    return low, high


def _day_bounds(low, high):
    if low == high:
        yield low, high
    while low < high:
        boundary = high if low.date() == date.max else datetime.combine(low.date() + timedelta(days=1), time.min)
        end = min(high, boundary)
        yield low, end
        low = end


class _DowntimeIndex:
    """Parse a machine's saved intervals once; retain raw error rows in source order."""

    def __init__(self, rows):
        intervals, self.errors = [], []
        for row in rows:
            if row.get("status") == "cancelled":
                continue
            try:
                start, end = instant(row["start_time"]), instant(row["end_time"])
            except (ValueError, TypeError, KeyError):
                self.errors.append((row, None, None))
                continue
            if start >= end:
                self.errors.append((row, None, None))
            elif row.get("status") != "active":
                self.errors.append((row, start, end))
            else:
                intervals.append((start, end))
        # apply_resource exposes only the union of valid downtime windows; no
        # record identity or other row metadata is part of this projection.
        self.intervals = union(intervals)
        self.starts = [start for start, _end in self.intervals]
        self.ends = [end for _start, end in self.intervals]

    def between(self, low, high):
        for row, start, end in self.errors:
            if start is None or start < high and end > low:
                # The first applicable raw error keeps the original error and
                # missing-field precedence; later valid rows cannot change it.
                return [row]
        first, last = bisect_right(self.ends, low), bisect_left(self.starts, high)
        return [{"status": "active", "start_time": start, "end_time": end}
                for start, end in self.intervals[first:last]]


def _aggregate(days, basis, source):
    known = [day for day in days if day["state"] == "available"]
    complete = len(known) == len(days)
    known_windows = [window for day in known for window in day["windows"]]
    result = {"state": "available" if complete else "partial" if known else "unavailable", "basis": basis,
              "windows": known_windows if complete else None,
              "known_windows": known_windows,
              "days": days, "known_days": len(known), "unknown_days": len(days) - len(known), "source": source}
    result.update({key: sum(day[key] for day in known) if complete else None for key in _MEASURES})
    issues, seen = [], set()
    for day in days:
        for item in day["issues"]:
            key = (item["code"], item.get("policy_date"), item.get("missing_fact"))
            if key not in seen:
                issues.append(item)
                seen.add(key)
    result["issues"] = issues
    return result


class ArchivedCalendar:
    """One archive/index/engine for streaming resource projections in one read.

    ``resources`` contain ``kind``, permanent ``ref`` and the archive's ``saved_id``.
    Every day is available (including true zero) or unavailable. A partial whole
    window retains its known days/windows; its total capacity remains unknown.
    """

    def __init__(self, archive, *, source_ref=None, coverage=None, metadata_basis="saved_archive", facts=None):
        self.archive, self._tables, self.facts = archive, {}, facts
        self.coverage = _bounds(coverage["start"], coverage["end"]) if coverage is not None else None
        versions = self.table("SchemaVersion") or []
        rows = [row for row in versions if row.get("id") == 1]
        self.version = rows[0].get("version") if len(rows) == 1 else None
        if type(self.version) is not int or self.version < 1:
            self.version = None
        self.source = {"source_ref": source_ref, "schema_version": self.version,
                       "time_basis": "factory_local", "metadata_basis": metadata_basis,
                       "coverage": {"start": self.coverage[0].isoformat(), "end": self.coverage[1].isoformat()}
                       if self.coverage is not None else None}
        refs = self.table("WorkbenchEntityRefs") or []
        self.bindings = {(row["kind"], row["ref"]): row["entity_key"] for row in refs if row.get("active") == 1}
        self.records = {kind: {row[kind + "_id"]: row for row in self.table(name) or []}
                        for kind, name in (("machine", "Machines"), ("operator", "Operators"))}
        self.downtimes = defaultdict(list)
        rows = self.table("MachineDowntimes")
        self.downtimes_known = rows is not None
        for row in rows or []:
            self.downtimes[row["machine_id"]].append(row)
        self._downtime_indexes = {}
        tables = {name: self.table(name) for name in (
            "WorkCalendar", "OperatorCalendar", "WorkbenchOperatorProfiles", "WorkbenchShiftProfiles",
            "WorkbenchShiftPatternDays", "WorkbenchShiftDayPeriods", "WorkbenchCalendarDefaults")}
        # 坏日期等日历内容错误由引擎留到读取那天再报；这里只剩保存表结构损坏（缺列、类型不对）让整份引擎不可用。
        try:
            self.engine = _SavedCalendarEngine(tables, self.version)
        except (ValueError, TypeError, KeyError, OverflowError):
            self.engine = None
        self._global_days = {}
        self._shift_days = {}

    def table(self, name):
        """Decode each saved table once; trial dictionary rows are already decoded."""
        if name not in self._tables:
            if self.facts is not None:
                self._tables[name] = self.facts.table(name)
                return self._tables[name]
            rows = self.archive["tables"].get(name)
            if rows is None or type(rows) is list and all(type(row) is dict for row in rows):
                self._tables[name] = rows
            elif "columns" in self.archive:
                columns = self.archive["columns"].get(name)
                if type(columns) is not list or any(type(row) is not list or len(row) != len(columns) for row in rows):
                    corrupt()
                self._tables[name] = [dict(zip(columns, row)) for row in rows]
            else:
                self._tables[name] = archived_table(self.archive, name)
        return self._tables[name]

    def _policy_day(self, low, high, operator_id=None, *, engine: _SavedCalendarEngine):
        key = (low, high)
        if operator_id is None and key in self._global_days:
            return self._global_days[key]
        first = low.date() - timedelta(days=1) if low.date() > date.min else low.date()
        shift_key = None
        if operator_id is not None:
            op_id = engine._normalize_text(operator_id)
            member = engine.members.get(op_id)
            # 个人日历表坏了时空索引不代表“没有个人日历”，不能借用全局或同班表的结果。
            if (op_id == operator_id and engine._personal_error is None
                    and engine.tables["OperatorCalendar"] is not None
                    and engine.tables["WorkbenchOperatorProfiles"] is not None
                    and all((who, day) not in engine.personal_rows
                            for day in (first.isoformat(), low.date().isoformat()) for who in (op_id, None))):
                profile_id = member.get("shift_profile_id") if member is not None else None
                if profile_id is None:
                    base = self._policy_day(low, high, engine=engine)
                    if base["state"] == "available":
                        # Windows/provenance are the same saved policy; resource
                        # availability only changes a new outer projection.
                        return base
                else:
                    shift_key = (low, high, profile_id)
                    if shift_key in self._shift_days:
                        return self._shift_days[shift_key]
        base = policy_projection(engine, first, low.date(), low, high, operator_id)
        if base["state"] != "available":
            for day in (first, low.date()):
                name = engine.missing_policies.get((operator_id, day.isoformat()))
                name = name or engine.missing_policies.get((None, day.isoformat()))
                if name is not None:
                    base = unavailable(base["basis"], "calendar_unavailable")
                    base["issues"][0].update(missing_fact=name, policy_date=day.isoformat())
                    break
        if operator_id is None:
            self._global_days[key] = base
        elif shift_key is not None and base["state"] == "available":
            self._shift_days[shift_key] = base
        return base

    def _resource_day(self, resource, low, high):
        kind, ref, saved_id = resource["kind"], resource["ref"], resource.get("saved_id")
        basis = "global_calendar_machine_availability" if kind == "machine" else "personal_or_operator_shift_calendar"
        if saved_id is None or self.bindings.get((kind, ref)) != saved_id:
            result = unavailable(basis, "resource_missing")
            result["issues"][0].update(missing_fact="WorkbenchEntityRefs." + kind, resource_ref=ref)
        elif self.coverage is not None and not (self.coverage[0] <= low and high <= self.coverage[1]):
            result = unavailable(basis, "calendar_unavailable")
            result["issues"][0]["missing_fact"] = "calendar_coverage"
        elif self.engine is None:
            result = unavailable(basis, "calendar_invalid")
        elif kind == "machine" and not self.downtimes_known:
            result = unavailable(basis, "calendar_unavailable")
            result["issues"][0]["missing_fact"] = "MachineDowntimes"
        else:
            base = self._policy_day(low, high, saved_id if kind == "operator" else None, engine=self.engine)
            result = apply_resource(base, self.records[kind].get(saved_id), kind,
                                    self._machine_downtimes(saved_id, low, high) if kind == "machine" else [], low, high)
        return {**result, "date": low.date().isoformat(), "start": low.isoformat(), "end": high.isoformat(),
                "source": self.source}

    def _machine_downtimes(self, saved_id, low, high):
        if saved_id not in self._downtime_indexes:
            self._downtime_indexes[saved_id] = _DowntimeIndex(self.downtimes[saved_id])
        return self._downtime_indexes[saved_id].between(low, high)

    def iter_resources(self, resources, start, end):
        """Stream complete resources; callers may consume summaries and discard days."""
        low, high = _bounds(start, end)
        for resource in resources:
            days = [self._resource_day(resource, first, last) for first, last in _day_bounds(low, high)]
            basis = "global_calendar_machine_availability" if resource["kind"] == "machine" else "personal_or_operator_shift_calendar"
            yield resource["ref"], {**_aggregate(days, basis, self.source), "resource_ref": resource["ref"],
                                    "resource_type": resource["kind"]}
            # Global policies remain reusable; personnel policy cells do not
            # accumulate across a complete streaming cohort.
            if self.engine is not None and resource["kind"] == "operator":
                self.engine.discard_operator_policy(resource.get("saved_id"))
