"""One frozen resource cohort, calendar and interval index for each decision read."""

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from core.models.workbench_run_candidate import local_time, reject
from core.services.workbench.facts.archived_calendar import ArchivedCalendar, archived_calendar_tables
from core.services.workbench.facts.decision_read_models import build_resource_metrics_from_summaries
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.resource_calendar import normalize_resource_calendar
from core.services.workbench.facts.resource_pressure import DEFAULT_PRESSURE_THRESHOLD
from core.services.workbench.facts.resource_projection import ResourceTaskIndex, resource_summary

from .decision_impact import drill_target

KINDS = ("machine", "operator")
DELTA_FIELDS = ("available_hours", "occupied_hours", "summed_load_hours", "outside_calendar_hours", "overlap_hours",
                "utilization_ratio", "demand_ratio", "peak_utilization", "span_occupied_hours", "span_summed_hours", "span_overlap_hours", "overlap_span_hours")


def resource_deltas(before, after, fields=DELTA_FIELDS):
    return {key: after[key] - before[key] if before.get(key) is not None and after.get(key) is not None else None for key in fields}


class _LazyArchivedCalendar:
    """Load and decode calendar_json only when non-precomputed window or period slicing runs."""

    def __init__(self, source):
        self._source = source
        self._inner = None

    def iter_resources(self, resources, start, end):
        if self._inner is None:
            self._inner = ArchivedCalendar(archived_calendar_tables(self._source.calendar_archive),
                                           source_ref=self._source.run["run_ref"])
        return self._inner.iter_resources(resources, start, end)


@dataclass(frozen=True)
class ResourceWindowInput:
    """One fixed resource window: its calendar, frozen resource cohort and each compared side's arranged tasks."""
    start: Any
    end: Any
    calendar: Any
    resources: List[Dict[str, Any]]
    reference_available: bool
    side_tasks: Callable[[str], List[Dict[str, Any]]]
    task_intervals: Callable[[str], Dict[str, Any]]
    computation_key: Callable[[str], str]


def decision_window_input(source):
    """A decision read's window: archived calendar, admission cohort and the reference/candidate sides."""
    calendar = _LazyArchivedCalendar(source)
    saved = {(item["kind"], item["ref"]): item["saved_id"] for item in source.context["resources"] if item["kind"] in KINDS}
    resources = [{**item, "saved_id": saved.get((item["kind"], item["ref"]))} for item in source.resource_cohort["resources"]]
    return ResourceWindowInput(
        source.scope["range_start"], source.scope["range_end"], calendar, resources, source.arrangement_available("reference"),
        side_tasks=lambda key: source.resource_before_tasks if key == "reference" else source.resource_tasks(key),
        task_intervals=source.task_intervals, computation_key=source.computation_key)


class ResourceWindowMetrics:
    """Per-resource windows, kind summaries and resource metrics of one ``ResourceWindowInput``."""

    def __init__(self, inputs):
        self.inputs = inputs
        self.start, self.end, self.calendar = inputs.start, inputs.end, inputs.calendar
        self._default_window_bounds = (local_time(self.start), local_time(self.end))
        self.resources = inputs.resources
        self._resource_by_ref = {row["ref"]: row for row in self.resources}
        self.tasks = {}
        self.indexes, self._window_rows, self._summaries, self._groups = {}, {}, {}, {}
        self._calendars = {}

    def _work_available(self, key):
        """Every compared candidate has its saved tasks; only the reference side may have no arrangement source."""
        return key != "reference" or self.inputs.reference_available

    def index(self, key):
        key = self.inputs.computation_key(key)
        if key not in self.indexes:
            if key not in self.tasks:
                self.tasks[key] = self.inputs.side_tasks(key)
            self.indexes[key] = ResourceTaskIndex(
                self.tasks[key], self.start, self.end, work_available=self._work_available(key),
                task_intervals=self.inputs.task_intervals(key), retain_statistics_values=False)
        return self.indexes[key]

    def resource(self, ref, kind):
        item = self._resource_by_ref.get(ref)
        if item is None or item["kind"] != kind:
            reject("entity_not_found", "该资源不在当前共同归档资源集合，请重新选择。", 404)
        return item

    def _ensure_windows(self, keys, resources, threshold):
        keys = list(dict.fromkeys(self.inputs.computation_key(key) for key in keys))
        pending = [resource for resource in resources if any((key, resource["ref"], threshold) not in self._window_rows for key in keys)]
        if not pending:
            return
        self._prepare_calendars(pending)
        for resource in pending:
            ref, calendar = resource["ref"], self._calendars[resource["ref"]]
            for key in keys:
                if (key, ref, threshold) not in self._window_rows:
                    self._window_rows[key, ref, threshold] = self.index(key).window(resource, calendar, threshold=threshold)

    def window_row(self, key, ref, threshold=DEFAULT_PRESSURE_THRESHOLD):
        """One resource's window on one side at one attention line; computed on first use through the shared window path."""
        self._ensure_windows([key], [self._resource_by_ref[ref]], threshold)
        return self._window_rows[self.inputs.computation_key(key), ref, threshold]

    def _prepare_calendars(self, resources):
        pending = [resource for resource in resources if resource["ref"] not in self._calendars]
        for ref, calendar in self.calendar.iter_resources(pending, self.start, self.end):
            self._calendars[ref] = normalize_resource_calendar(calendar, self.start, self.end)

    def resource_calendar(self, resource):
        self._prepare_calendars([resource])
        return self._calendars[resource["ref"]]

    def prepare_keys(self, keys):
        self._ensure_windows(keys, self.resources, DEFAULT_PRESSURE_THRESHOLD)

    def summary(self, key, kind, threshold=DEFAULT_PRESSURE_THRESHOLD):
        key = self.inputs.computation_key(key)
        if (key, kind, threshold) not in self._summaries:
            resources = [resource for resource in self.resources if resource["kind"] == kind]
            self._ensure_windows([key], resources, threshold)
            index = self.index(key)
            self._summaries[key, kind, threshold] = resource_summary(
                [self._window_rows[key, resource["ref"], threshold] for resource in resources], kind=kind,
                identity_issues=[item for item in index.identity_issues if item["kind"] == kind], work_available=index.work_available)
        return self._summaries[key, kind, threshold]

    def metrics(self, key):
        key = self.inputs.computation_key(key)
        summaries = {kind: self.summary(key, kind) for kind in KINDS}
        w_rows = {row["ref"]: self._window_rows[key, row["ref"], DEFAULT_PRESSURE_THRESHOLD] for row in self.resources}
        return build_resource_metrics_from_summaries(summaries, w_rows, self.resources, self._work_available(key))


class DecisionResources(ResourceWindowMetrics):
    """The decision workspace's resource reads: selected/reference pairs, coverage, drills and periods."""

    def __init__(self, source):
        super().__init__(decision_window_input(source))
        self.source = source
        self._seeded_cohorts = set()
        self._seeded_details = set()
        self._precomputed_metrics = {}
        self._precomputed_day_filter_summaries = {}
        self._precomputed_day_periods = {}

    def _seed_cohort(self, key):
        comp = self.inputs.computation_key(key)
        if comp in self._seeded_cohorts:
            return
        self._seeded_cohorts.add(comp)
        cohort = self.source.precomputed_resource_cohort(comp)
        if cohort is None:
            return
        for kind in KINDS:
            self._summaries[comp, kind, DEFAULT_PRESSURE_THRESHOLD] = cohort["summaries"][kind]
        self._precomputed_metrics[comp] = cohort["metrics"]

    def _seed_details(self, key):
        comp = self.inputs.computation_key(key)
        if comp in self._seeded_details:
            return
        self._seeded_details.add(comp)
        details = self.source.precomputed_resource_details(comp)
        if details is None:
            return
        for ref, row in details["window_rows"].items():
            if ref in self._resource_by_ref:
                row["label"] = self._resource_by_ref[ref]["label"]
            self._window_rows[comp, ref, DEFAULT_PRESSURE_THRESHOLD] = row
        for ref, d_summary in details["day_filter_summaries"].items():
            self._precomputed_day_filter_summaries[comp, ref] = d_summary
        for ref, periods in details["day_periods"].items():
            if ref in self._resource_by_ref:
                label = self._resource_by_ref[ref]["label"]
                for period in periods:
                    period["label"] = label
            self._precomputed_day_periods[comp, ref] = periods

    def prepare_keys(self, keys):
        missing = []
        for key in keys:
            comp = self.inputs.computation_key(key)
            self._seed_cohort(comp)
            if comp not in self._precomputed_metrics:
                missing.append(key)
        if missing:
            super().prepare_keys(missing)

    def window_row(self, key, ref, threshold=DEFAULT_PRESSURE_THRESHOLD):
        if threshold == DEFAULT_PRESSURE_THRESHOLD:
            self._seed_details(key)
        return super().window_row(key, ref, threshold)

    def summary(self, key, kind, threshold=DEFAULT_PRESSURE_THRESHOLD):
        if threshold == DEFAULT_PRESSURE_THRESHOLD:
            self._seed_cohort(key)
        return super().summary(key, kind, threshold)

    def metrics(self, key):
        comp = self.inputs.computation_key(key)
        self._seed_cohort(comp)
        if comp in self._precomputed_metrics:
            return self._precomputed_metrics[comp]
        return super().metrics(comp)

    def pair(self, resource, threshold):
        before, after = (self.window_row(key, resource["ref"], threshold) for key in ("reference", self.source.selected_ref))
        return {"before": before, "after": after, "deltas": resource_deltas(before, after)}

    def _coverage_sets(self, key):
        source = self.source
        members = source.official_members
        official = set(members["operation_refs"])
        arranged = official if key == "reference" and source.comparison_mode == "admission_official" else (
            source.scheduled_refs(key) if key != "reference" or source.reference_ref else set())
        values = official_scope_coverage(official, arranged)
        admitted = source.operation_refs
        deferred = source.deferred_refs if key != "reference" or source.comparison_mode == "candidates" else source.reference_deferred_refs & admitted
        return members, values, admitted - arranged - deferred, deferred

    def coverage_operation_refs(self, key):
        _members, values, unplanned, deferred = self._coverage_sets(key)
        return {
            "missing_formal_operation_refs": values["missing_official_operations"],
            "unplanned_operation_refs": sorted(unplanned),
            "deferred_operation_refs": sorted(deferred),
        }

    def coverage(self, key, *, details=False):
        members, values, unplanned, deferred = self._coverage_sets(key)
        missing_refs = values["missing_official_operations"]
        result = {
            "formal_state": members["identity"]["state"],
            "formal_operation_count": values["official_operation_count"],
            "covered_formal_operation_count": values["covered_official_operation_count"],
            "missing_formal_operation_count": len(missing_refs),
            "formal_coverage_complete": values["covers_official_scope"],
            "unplanned_operation_count": len(unplanned),
            "deferred_operation_count": len(deferred),
        }
        if details:
            missing = set(missing_refs)
            result["missing_formal_arrangements"] = [{k: row[k] for k in (
                "operation_ref", "row_ref", "batch_ref", "batch_label", "process_label", "start", "end")}
                for row in self.source.official_tasks if row["operation_ref"] in missing] if missing else []
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
        if start is None and end is None:
            low, high = self._default_window_bounds
        else:
            low, high = local_time(start or self.start), local_time(end or self.end)
        intervals = source.task_intervals(key)
        if tasks is None:
            tasks = [row for row in self.task_group(key)[resource["ref"]]
                     if intervals[row["row_ref"]][0] < high and intervals[row["row_ref"]][1] > low]
        value = drill_target(
            source, tasks=tasks, batch_ref=None, before=key == "reference",
            window=(low.isoformat(), high.isoformat()), window_bounds=(low, high), task_intervals=intervals,
        )
        if value is None:
            return None
        value.update(resource_view=source.resource_view, resource_kind=resource["kind"], resource_ref=resource["ref"], comparison_tab="resources")
        return value

    def rows(self, kind, threshold):
        if threshold == DEFAULT_PRESSURE_THRESHOLD:
            self._seed_details(self.source.selected_ref)
            self._seed_details("reference")
        resources = [resource for resource in self.resources if resource["kind"] == kind]
        self._ensure_windows([self.source.selected_ref, "reference"], resources, threshold)
        return [{"resource_ref": res["ref"], "resource_kind": kind, "label": res["label"], **self.pair(res, threshold)}
                for res in resources]

    def period_facts(self, resource, *, threshold, grain="day", start=None, end=None):
        return self.index(self.source.selected_ref).period_facts(resource, self.resource_calendar(resource),
            threshold=threshold, grain=grain, start=start or self.start, end=end or self.end)

    def filter_summary(self, resource, *, threshold, grain, start, end, daily_peak):
        if grain == "day" and start == self.start and end == self.end:
            if threshold == DEFAULT_PRESSURE_THRESHOLD:
                comp = self.inputs.computation_key(self.source.selected_ref)
                self._seed_details(comp)
                if (comp, resource["ref"]) in self._precomputed_day_filter_summaries:
                    summary = self._precomputed_day_filter_summaries[comp, resource["ref"]]
                    if summary is not None:
                        return summary
                    return _period_summary(self._precomputed_day_periods[comp, resource["ref"]], daily_peak)
            summary = self.index(self.source.selected_ref).day_filter_summary(
                resource, self.resource_calendar(resource), threshold=threshold)
            if summary is not None:
                return summary
        return _period_summary(self.period_facts(resource, threshold=threshold, grain=grain, start=start, end=end), daily_peak)

    def periods(self, resource, *, threshold, grain="day", start=None, end=None, details=False, group_keys=None):
        low, high = start or self.start, end or self.end
        ref_comp = self.inputs.computation_key("reference")
        sel_comp = self.inputs.computation_key(self.source.selected_ref)
        if not details and threshold == DEFAULT_PRESSURE_THRESHOLD and grain == "day" and low == self.start and high == self.end:
            self._seed_details(ref_comp)
            self._seed_details(sel_comp)
            res_ref = resource["ref"]
            if (ref_comp, res_ref) in self._precomputed_day_periods and (sel_comp, res_ref) in self._precomputed_day_periods:
                before = [
                    row for row in self._precomputed_day_periods[ref_comp, res_ref]
                    if group_keys is None or row["group_key"] in group_keys
                ]
                after = before if ref_comp == sel_comp else [
                    row for row in self._precomputed_day_periods[sel_comp, res_ref]
                    if group_keys is None or row["group_key"] in group_keys
                ]
                return [
                    {**{key: selected[key] for key in ("key", "bucket_key", "group_key", "date", "grain", "start", "end", "placeholder")},
                     "before": previous, "after": selected, "deltas": resource_deltas(previous, selected)}
                    for previous, selected in zip(before, after)
                ]
        calendar = self.resource_calendar(resource)
        before = self.index("reference").periods(resource, calendar, threshold=threshold, grain=grain, start=low, end=high,
                                                details=details, group_keys=group_keys)
        if ref_comp == sel_comp:
            after = deepcopy(before) if details else before
        else:
            after = self.index(self.source.selected_ref).periods(resource, calendar, threshold=threshold, grain=grain, start=low, end=high,
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
