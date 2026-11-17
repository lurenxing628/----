"""Saved calendar facts projected through the existing factory-local rules.

``tables`` names the rows of each of ``CALENDAR_TABLES``: a run or trial archive's own copy
(``archived_calendar_tables``) or this transaction's current reads. A caller with a bounded
calendar declares its evaluable ``coverage`` instead. Nothing is read from a connection or
filled from a current resource/calendar directory.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, timedelta

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant, union
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES
from core.services.capacity.plan_calendar_windows import (
    apply_resource,
    policy_projection,
    resource_record_unavailable,
    unavailable,
)
from core.services.scheduler.calendar.engine import CalendarEngine
from core.shared.local_datetime import row_interval
from core.shared.strict_parse import is_exact_positive_int

from .calendar_inputs import calendar_inputs_from_archive_tables
from .production_capture import table_rows
from .resource_calendar import natural_days

CALENDAR_TABLES = ("SchemaVersion", "WorkbenchEntityRefs", "Machines", "Operators", "MachineDowntimes", "WorkCalendar",
                   "OperatorCalendar", "WorkbenchOperatorProfiles", "WorkbenchShiftProfiles", "WorkbenchShiftPatternDays",
                   "WorkbenchCalendarDefaults")
_MEASURES = ("available_hours", "effective_hours", "normal_available_hours", "normal_effective_hours",
             "urgent_available_hours", "urgent_effective_hours")


def archived_calendar_tables(archive):
    """The calendar tables of an admitted archive, or of its saved calendar part, with named rows."""
    return {name: table_rows(archive, name) for name in CALENDAR_TABLES}


def _bounds(start, end):
    low, high = instant(start), instant(end)
    if low > high:
        raise WorkbenchCommandRejected("invalid_input", "资源比较窗口的结束不能早于开始。", 422)
    last = (high - timedelta(microseconds=1)).date() if low < high else low.date()
    if (last - low.date()).days + 1 > MAX_CALENDAR_DATES:
        raise WorkbenchCommandRejected("invalid_input", "资源比较窗口超过 3660 天，请缩小时间范围。", 422)
    return low, high


class DowntimeIndex:
    """One machine's downtime rows read once: ``intervals`` is the sorted, disjoint union of its active windows.

    Cancelled rows are not downtime.
    """

    def __init__(self, rows):
        self.intervals = union(row_interval(row) for row in rows if row["status"] == "active")
        self.starts = [start for start, _end in self.intervals]
        self.ends = [end for _start, end in self.intervals]

    def overlaps(self, low, high):
        return bisect_right(self.ends, low) < bisect_left(self.starts, high)

    def between(self, low, high):
        """The union's windows intersecting ``[low, high)``."""
        return self.intervals[bisect_right(self.ends, low):bisect_left(self.starts, high)]


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
    """One calendar table set/index/engine for streaming resource projections in one read.

    ``resources`` contain ``kind``, permanent ``ref`` and the archive's ``saved_id``.
    Every day is available (including true zero) or unavailable. A partial whole
    window retains its known days/windows; its total capacity remains unknown.
    """

    def __init__(self, tables, *, source_ref=None, coverage=None, metadata_basis="saved_archive"):
        self.tables = tables
        self.coverage = _bounds(coverage["start"], coverage["end"]) if coverage is not None else None
        versions = [row for row in tables["SchemaVersion"] if row["id"] == 1]
        self.version = (versions[0]["version"]
                        if len(versions) == 1 and is_exact_positive_int(versions[0]["version"]) else None)
        self.source = {"source_ref": source_ref, "schema_version": self.version,
                       "time_basis": "factory_local", "metadata_basis": metadata_basis,
                       "coverage": {"start": self.coverage[0].isoformat(), "end": self.coverage[1].isoformat()}
                       if self.coverage is not None else None}
        self.bindings = {(row["kind"], row["ref"]): row["entity_key"]
                         for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
        self.records = {kind: {row[kind + "_id"]: row for row in tables[name]}
                        for kind, name in (("machine", "Machines"), ("operator", "Operators"))}
        self.downtimes = defaultdict(list)
        for row in tables["MachineDowntimes"]:
            self.downtimes[row["machine_id"]].append(row)
        self._downtime_indexes = {}
        # 坏日期等日历内容错误由引擎留到读取那天再报，逐日投影为 calendar_invalid。建引擎要用的表、列与班次轮换日
        # 偏移，归档在准入处已核过（production_capture.validate_production_archive），本事务读的是库里的行；
        # 决策读模型存的日历是自派生副本，坏了照原样报错。
        self.engine = CalendarEngine(calendar_inputs_from_archive_tables(tables))
        self._global_days = {}
        self._shift_days = {}

    def _policy_day(self, low, high, operator_id=None):
        engine, key = self.engine, (low, high)
        if operator_id is None and key in self._global_days:
            return self._global_days[key]
        first = low.date() - timedelta(days=1) if low.date() > date.min else low.date()
        shift_key = None
        if operator_id is not None:
            op_id = engine._normalize_text(operator_id)
            profile = engine.shift_profiles.get(op_id)
            if (op_id == operator_id
                    and engine.inputs.personal_days is not None
                    and engine.inputs.operator_profiles is not None
                    and all((op_id, day) not in engine.personal_rows
                            for day in (first.isoformat(), low.date().isoformat()))):
                profile_id = profile["shift_profile_id"] if profile is not None else None
                if profile_id is None:
                    return self._policy_day(low, high)
                else:
                    shift_key = (low, high, profile_id)
                    if shift_key in self._shift_days:
                        return self._shift_days[shift_key]
        base = policy_projection(engine, first, low.date(), low, high, operator_id)
        if operator_id is None:
            self._global_days[key] = base
        elif shift_key is not None:
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
        else:
            raw_record = self.records[kind].get(saved_id)
            rejected = resource_record_unavailable(raw_record, basis)
            if rejected is not None:
                result = rejected
            else:
                base = self._policy_day(low, high, saved_id if kind == "operator" else None)
                result = apply_resource(
                    base,
                    raw_record,
                    kind,
                    self.downtime_index(saved_id).between(low, high) if kind == "machine" else [],
                    low,
                    high,
                )
        return {**result, "date": low.date().isoformat(), "start": low, "end": high,
                "source": self.source}

    def global_summary(self, start, end):
        """The global calendar over a window by natural day, aggregated like a resource's window.

        A machine's day is this same global day with its downtime applied, so the days resources
        already streamed are reused; a broken policy leaves only its own days unknown.
        """
        low, high = _bounds(start, end)
        days = [self._policy_day(first, last) for first, last in natural_days(low, high)]
        return _aggregate(days, "global_calendar", self.source)

    def downtime_index(self, machine_id):
        """The machine's parsed downtime, shared by resource days and task feasibility checks."""
        if machine_id not in self._downtime_indexes:
            self._downtime_indexes[machine_id] = DowntimeIndex(self.downtimes[machine_id])
        return self._downtime_indexes[machine_id]

    def iter_resources(self, resources, start, end):
        """Stream complete resources; callers may consume summaries and discard days."""
        low, high = _bounds(start, end)
        for resource in resources:
            days = [self._resource_day(resource, first, last) for first, last in natural_days(low, high)]
            basis = "global_calendar_machine_availability" if resource["kind"] == "machine" else "personal_or_operator_shift_calendar"
            yield resource["ref"], {**_aggregate(days, basis, self.source), "resource_ref": resource["ref"],
                                    "resource_type": resource["kind"]}
            # Global policies remain reusable; personnel policy cells do not
            # accumulate across a complete streaming cohort.
            if resource["kind"] == "operator":
                self.engine.discard_operator_policy(resource.get("saved_id"))
