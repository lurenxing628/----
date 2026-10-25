"""One frozen resource cohort, calendar and interval index for each decision read."""

from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict

from core.models.workbench_run_candidate import local_time, reject
from core.services.capacity.plan_calendar_intervals import instant
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.decision_metrics import RESOURCE_METRICS, metric_value
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.resource_calendar import normalize_resource_calendar
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_summary,
)

from .decision_impact import drill_target

KINDS = ("machine", "operator")
DELTA_FIELDS = ("available_hours", "occupied_hours", "summed_load_hours", "outside_calendar_hours", "overlap_hours",
                "utilization_ratio", "demand_ratio", "peak_utilization", "span_occupied_hours", "span_summed_hours", "span_overlap_hours", "overlap_span_hours")
_FLAGS = {"high_pressure_count": "high_pressure", "zero_capacity_task_count": "zero_capacity_task", "conflict_resource_count": "conflict"}


def _metric_known(row, field):
    if field in _FLAGS:
        return row[_FLAGS[field]] is not None
    if field == "unknown_day_resource_count":
        return row["unknown_days"] is not None
    if field == "used_resource_count":
        return row["operation_count"] is not None
    if field == "utilization_ratio":
        return row["available_hours"] is not None and row["occupied_hours"] is not None
    if field == "balance_cv":
        return row["available_hours"] is not None and (row["available_hours"] == 0 or row["occupied_hours"] is not None)
    return row[field] is not None


def resource_deltas(before, after, fields=DELTA_FIELDS):
    return {key: after[key] - before[key] if before.get(key) is not None and after.get(key) is not None else None for key in fields}


class DecisionResources:
    def __init__(self, source, *, calendar=None):
        self.source = source
        self.start, self.end = source.scope["range_start"], source.scope["range_end"]
        self.calendar = (
            ArchivedCalendar(source.calendar_archive, source_ref=source.run["run_ref"])
            if calendar is None
            else calendar
        )
        saved = {(item["kind"], item["ref"]): item["saved_id"] for item in source.context["resources"] if item["kind"] in KINDS}
        self.resources = [{**item, "saved_id": saved.get((item["kind"], item["ref"]))} for item in source.resource_cohort["resources"]]
        self._resource_by_ref = {row["ref"]: row for row in self.resources}
        self.tasks = {}
        self._available = {source.computation_key(row["candidate_ref"]): row["status"] == "completed" for row in source.rows}
        self._available[source.computation_key("reference")] = source.baseline["state"] == "available"
        self.indexes, self._window_rows, self._summaries, self._groups = {}, {}, {}, {}
        self._calendars = {}
        self._calendar_times = {}
        self.pressure_threshold = 0.9

    def configure(self, threshold):
        if self.pressure_threshold != threshold:
            self.pressure_threshold = threshold
            self.indexes, self._window_rows, self._summaries = {}, {}, {}

    def index(self, key):
        key = self.source.computation_key(key)
        if key not in self.indexes:
            if key not in self.tasks:
                self.tasks[key] = self.source.resource_before_tasks if key == "reference" else self.source.resource_tasks(key)
            self.indexes[key] = ResourceTaskIndex(self.tasks[key], self.start, self.end, work_available=self._available[key],
                                                 pressure_threshold=self.pressure_threshold, task_intervals=self.source.task_intervals(key),
                                                 retain_statistics_values=False)
        return self.indexes[key]

    def resource(self, ref, kind):
        item = self._resource_by_ref.get(ref)
        if item is None or item["kind"] != kind:
            reject("entity_not_found", "该资源不在当前共同归档资源集合，请重新选择。", 404)
        return item

    def _ensure_windows(self, keys, resources):
        keys = list(dict.fromkeys(self.source.computation_key(key) for key in keys))
        pending = [resource for resource in resources if any((key, resource["ref"]) not in self._window_rows for key in keys)]
        if not pending:
            return
        self._prepare_calendars(pending)
        for resource in pending:
            ref, calendar = resource["ref"], self._calendars[resource["ref"]]
            for key in keys:
                if (key, ref) not in self._window_rows:
                    self._window_rows[key, ref] = self.index(key).window(resource, calendar)

    def _prepare_calendars(self, resources):
        pending = [resource for resource in resources if resource["ref"] not in self._calendars]
        for ref, calendar in self.calendar.iter_resources(pending, self.start, self.end):
            self._calendars[ref] = normalize_resource_calendar(calendar, self.start, self.end, parse_time=self._calendar_time)

    def _calendar_time(self, value):
        if not isinstance(value, str):
            return instant(value)
        parsed = self._calendar_times.get(value)
        if parsed is None:
            parsed = instant(value)
            self._calendar_times[value] = parsed
        return parsed

    def resource_calendar(self, resource):
        self._prepare_calendars([resource])
        return self._calendars[resource["ref"]]

    def prepare_keys(self, keys):
        self._ensure_windows(keys, self.resources)

    def summary(self, key, kind):
        key = self.source.computation_key(key)
        if (key, kind) not in self._summaries:
            resources = [resource for resource in self.resources if resource["kind"] == kind]
            self._ensure_windows([key], resources)
            index = self.index(key)
            self._summaries[key, kind] = resource_summary(
                [self._window_rows[key, resource["ref"]] for resource in resources], kind=kind,
                identity_issues=[item for item in index.identity_issues if item["kind"] == kind], work_available=index.work_available)
        return self._summaries[key, kind]

    def pair(self, resource):
        selected = self.source.selected_ref
        self._ensure_windows(["reference", selected], [resource])
        before = self._window_rows[self.source.computation_key("reference"), resource["ref"]]
        after = self._window_rows[self.source.computation_key(selected), resource["ref"]]
        return {"before": dict(before), "after": dict(after), "deltas": resource_deltas(before, after)}

    def metrics(self, key):
        key = self.source.computation_key(key)
        result = {}
        for kind in KINDS:
            summary = self.summary(key, kind)
            total = summary["resource_count"]
            resources = [row for row in self.resources if row["kind"] == kind]
            for field, _label, _unit, _precision, _improvement, _common in RESOURCE_METRICS:
                value = summary[field]
                missing_work = summary["unknown_workload_count"] > 0 or not self.index(key).work_available
                empty = (total == 0 and not missing_work or field == "balance_cv" and summary["balance_state"] == "not_applicable"
                         or field == "utilization_ratio" and summary["available_hours"] == 0 and not missing_work)
                known_refs = [row["ref"] for row in resources if _metric_known(self._window_rows[key, row["ref"]], field)]
                unknown = total - len(known_refs)
                state = "not_applicable" if empty else "complete" if value is not None else "partial" if known_refs else "unavailable"
                if field == "balance_cv":
                    state = summary["balance_state"]
                issues = summary["issues"]
                reason = (summary["balance_reason"] if field == "balance_cv" else
                          {"code": "resource_evidence_incomplete", "message": "归档班表、任务时间或资源身份缺项，显示可核对的已知小计。"}
                          if value is None and not empty else {"code": "zero_available_capacity", "message": "共同资源窗口内没有正容量，占用率不适用。"}
                          if field == "utilization_ratio" and empty else None)
                if field == "zero_capacity_task_count" and value is None and any(
                    self._window_rows[key, row["ref"]]["zero_capacity_reason"] is not None for row in resources):
                    reason = {"code": "actual_work_fragments_not_recorded", "message": "零容量时段的安排跨度未提供实际工作片段，工作证据未知。"}
                item = metric_value(value, total=total, unknown=unknown, subtotal=summary.get("known_" + field), state=state,
                                    scope="fixed_resource_window", reason=reason, metric_version=RESOURCE_METRIC_VERSION)
                item.update(covered_resource_refs=known_refs, resource_kind=kind, issues=issues,
                            unknown_workload_count=summary["unknown_workload_count"])
                if field == "utilization_ratio":
                    item.update(numerator_hours=summary["numerator_hours"], denominator_hours=summary["denominator_hours"])
                result[kind + "_" + field] = item
        return result

    def coverage(self, key, *, details=False):
        source = self.source
        official_tasks = self.source.official["tasks"] if details else []
        members = source.official_members
        official = set(members["operation_refs"])
        arranged = official if key == "reference" and source.comparison_mode == "admission_official" else (
            source.scheduled_refs(key) if key != "reference" or source.reference_ref else set())
        values = official_scope_coverage(official, arranged)
        admitted = set(source.scope["operation_refs"])
        deferred = source.deferred_refs if key != "reference" or source.comparison_mode == "candidates" else source.reference_deferred_refs & admitted
        result = {"formal_state": members["identity"]["state"],
                  "formal_operation_count": values["official_operation_count"],
                  "covered_formal_operation_count": values["covered_official_operation_count"],
                  "missing_formal_operation_refs": values["missing_official_operations"],
                  "formal_coverage_complete": values["covers_official_scope"],
                  "unplanned_operation_refs": sorted(admitted - arranged - deferred), "deferred_operation_refs": sorted(deferred)}
        if details:
            missing = set(values["missing_official_operations"])
            result["missing_formal_arrangements"] = [{key: row[key] for key in (
                "operation_ref", "row_ref", "batch_ref", "batch_label", "process_label", "start", "end")}
                for row in official_tasks if row["operation_ref"] in missing]
        return result

    def overview_coverage(self, key):
        return {"machine": self.summary(key, "machine"), "operator": self.summary(key, "operator"), "formal": self.coverage(key)}

    def task_group(self, key):
        key = self.source.computation_key(key)
        if key not in self._groups:
            self.index(key)
            grouped = defaultdict(list)
            rows = self.tasks[key]
            for row in rows:
                if row["source"] == "external":
                    continue
                for kind in KINDS:
                    value = row[kind]
                    if value is not None and value["ref"] is not None:
                        grouped[value["ref"]].append(row)
            self._groups[key] = grouped
        return self._groups[key]

    def drill(self, key, resource, *, tasks=None, start=None, end=None):
        source = self.source
        low, high = local_time(start or self.start), local_time(end or self.end)
        if tasks is None:
            tasks = self.task_group(key)[resource["ref"]]
            tasks = [row for row in tasks if row["start"] is None or row["end"] is None or row.get("interval_comparable") is False or
                     local_time(row["start"]) < high and local_time(row["end"]) > low]
        value = drill_target(source, tasks=tasks, batch_ref=None, before=key == "reference", window=(low.isoformat(), high.isoformat()))
        if value is None:
            return None
        value.update(resource_view=source.resource_view, resource_kind=resource["kind"], resource_ref=resource["ref"], comparison_tab="resources")
        return value

    def rows(self, kind):
        resources = [resource for resource in self.resources if resource["kind"] == kind]
        self._ensure_windows([self.source.selected_ref, "reference"], resources)
        result = []
        for resource in resources:
            ref = resource["ref"]
            row = {"resource_ref": ref, "resource_kind": kind, "label": resource["label"], **self.pair(resource)}
            result.append(row)
        return result

    def period_facts(self, resource, *, grain="day", start=None, end=None):
        return self.index(self.source.selected_ref).period_facts(resource, self.resource_calendar(resource),
            grain=grain, start=start or self.start, end=end or self.end)

    def filter_summary(self, resource, *, grain, start, end, daily_peak):
        if grain == "day" and start == self.start and end == self.end:
            summary = self.index(self.source.selected_ref).day_filter_summary(resource, self.resource_calendar(resource))
            if summary is not None:
                return summary
        return _period_summary(self.period_facts(resource, grain=grain, start=start, end=end), daily_peak)

    def periods(self, resource, *, grain="day", start=None, end=None, details=False, group_keys=None):
        low, high = start or self.start, end or self.end
        calendar = self.resource_calendar(resource)
        before = self.index("reference").periods(resource, calendar, grain=grain, start=low, end=high,
                                                details=details, group_keys=group_keys)
        if self.source.computation_key("reference") == self.source.computation_key(self.source.selected_ref):
            # Detailed sides receive separate drill locations written in place below,
            # so each side owns its task/conflict dicts; plain cells are read-only.
            after = deepcopy(before) if details else before
        else:
            after = self.index(self.source.selected_ref).periods(resource, calendar, grain=grain, start=low, end=high,
                                                              details=details, group_keys=group_keys)
        result = []
        for previous, selected in zip(before, after):
            value = {**{key: selected[key] for key in ("key", "bucket_key", "group_key", "date", "grain", "start", "end", "placeholder")},
                     "before": previous, "after": selected, "deltas": resource_deltas(previous, selected)}
            if details:
                value["drill"] = {"selected": self.drill(self.source.selected_ref, resource, start=value["start"], end=value["end"]),
                                  "reference": self.drill("reference", resource, start=value["start"], end=value["end"])}
                for key, side in (("reference", previous), (self.source.selected_ref, selected)):
                    lookup = {row["row_ref"]: row for row in side["tasks"]}
                    for task in side["tasks"]:
                        task["drill"] = self.drill(key, resource, tasks=[task], start=value["start"], end=value["end"])
                        if task["drill"] is not None:
                            task["drill"].update(operation_ref=task["operation_ref"], selected_row_ref=task["row_ref"])
                    for conflict in side["conflicts"]:
                        rows = [lookup[ref] for ref in conflict["row_refs"]]
                        conflict["drill"] = self.drill(key, resource, tasks=rows, start=conflict["start"], end=conflict["end"])
            result.append(value)
        return result


def _period_summary(periods, daily_peak):
    values = periods
    state = "complete" if all(row["state"] == "complete" for row in values) else "unavailable" if all(
        row["state"] == "unavailable" for row in values) else "partial"
    result: Dict[str, Any] = {"state": state}
    for field in ("high_pressure", "demand_overload", "zero_capacity_task", "conflict"):
        flags = [row[field] for row in values]
        result[field] = True if True in flags else None if None in flags else False
    for field in ("high_pressure_period_count", "demand_overload_period_count", "conflict_period_count"):
        counts = [row[field] for row in values]
        result[field] = sum(counts) if all(value is not None for value in counts) else None
    peaks = [row["utilization_ratio"] for row in values if row["utilization_ratio"] is not None]
    result["period_peak_utilization"] = max(peaks) if peaks and result["state"] == "complete" else None
    result["daily_peak_utilization"] = daily_peak
    result["high_pressure_periods"] = [period for row in values for period in row["high_pressure_periods"]]
    result["unknown_period_count"] = sum(row["state"] != "complete" for row in values)
    return result
