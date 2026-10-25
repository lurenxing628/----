"""One frozen resource cohort, calendar and interval index for each decision read."""

from collections import defaultdict
from copy import deepcopy
from math import isfinite
from typing import Any, Dict, Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.capacity.plan_calendar_intervals import instant
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_metrics import RESOURCE_METRICS, metric_value
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    normalize_resource_calendar,
    resource_period_bounds,
    resource_summary,
)

from .decision_impact import drill_target
from .decision_queries import parse_page

KINDS = ("machine", "operator")
SORTS = ("after_utilization", "utilization_delta", "after_peak_utilization", "after_demand_hours", "after_available_hours", "label")
PRESSURE_FILTERS = ("all", "high_pressure", "demand_overload", "zero_capacity", "conflicts", "unknown")
GRAINS = ("hour", "day", "shift", "week")
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


def normalize_resource_filters(section, *, resource_kind="machine", resource_ref=None, pressure_filter="all", sort="after_peak_utilization", order="desc",
                               grain="day", pressure_threshold: Union[float, str] = 0.9, display_start=None, display_end=None, bucket_start=None, bucket_end=None):
    if section not in ("resources", "resource-days") or resource_kind not in KINDS:
        reject("invalid_input", "请选择设备或人员资源明细。", 422)
    if resource_ref is not None:
        reference(resource_ref)
    if grain not in GRAINS or isinstance(pressure_threshold, bool):
        reject("invalid_input", "资源粒度或高负荷阈值无效，请重新选择。", 422)
    try:
        threshold = float(pressure_threshold)
    except (TypeError, ValueError):
        reject("invalid_input", "高负荷阈值请选择大于0且不超过100%的比例。", 422)
    if not isfinite(threshold) or not 0 < threshold <= 1:
        reject("invalid_input", "高负荷阈值请选择大于0且不超过100%的比例。", 422)
    for first, last in ((display_start, display_end), (bucket_start, bucket_end)):
        if (first is None) != (last is None):
            reject("invalid_input", "资源时段需要完整且有效的起点和终点。", 422)
        if first is not None:
            try:
                ordered = local_time(first) < local_time(last)
            except ValueError:
                reject("invalid_input", "资源时段需要完整且有效的起点和终点。", 422)
            if not ordered:
                reject("invalid_input", "资源时段需要完整且有效的起点和终点。", 422)
    if display_start is not None and grain != "hour" or bucket_start is not None and section != "resource-days":
        reject("invalid_input", "当前资源页签或粒度不支持该时段筛选。", 422)
    common = {"section": section, "resource_kind": resource_kind, "resource_ref": resource_ref, "grain": grain,
              "pressure_threshold": threshold, "display_start": display_start, "display_end": display_end,
              "bucket_start": bucket_start, "bucket_end": bucket_end}
    if section == "resource-days":
        if resource_ref is None:
            reject("invalid_input", "请选择一个资源后查看逐日明细。", 422)
        return common
    if pressure_filter not in PRESSURE_FILTERS or sort not in SORTS or order not in ("asc", "desc"):
        reject("invalid_input", "资源筛选或排序条件无效，请重新选择。", 422)
    return {**common, "pressure_filter": pressure_filter, "sort": sort, "order": order}


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
            # Detailed sides receive separate public drill locations. Deep copy
            # preserves each side's task/reservation links without changing stats.
            after = deepcopy(before) if details else [dict(row) for row in before]
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


def _resource_matches(row, filters):
    if filters["resource_ref"] is not None and row["resource_ref"] != filters["resource_ref"]:
        return False
    field = {"high_pressure": "high_pressure", "demand_overload": "demand_overload", "zero_capacity": "zero_capacity_task", "conflicts": "conflict"}.get(filters["pressure_filter"])
    if field is not None:
        return row["filter_summary"][field] is True
    if filters["pressure_filter"] == "unknown":
        return row["filter_summary"]["state"] in ("partial", "unavailable")
    return True


def _sort_value(row, sort):
    if sort == "label":
        return row["label"]
    if sort == "utilization_delta":
        return row["deltas"]["utilization_ratio"]
    field = {"after_utilization": "utilization_ratio", "after_peak_utilization": "peak_utilization",
             "after_demand_hours": "summed_load_hours", "after_available_hours": "available_hours"}[sort]
    return row["after"][field]


def _ordered(rows, sort, order):
    rows = sorted(rows, key=lambda item: item["resource_ref"])
    known = [row for row in rows if _sort_value(row, sort) is not None]
    unknown = [row for row in rows if _sort_value(row, sort) is None]
    return sorted(known, key=lambda row: _sort_value(row, sort), reverse=order == "desc") + unknown


def _buckets(start, end, grain):
    return [{"key": first.date().isoformat() if grain == "shift" else grain + ":" + first.isoformat() + "/" + last.isoformat(),
             "start": first.isoformat(), "end": last.isoformat(), "date": first.date().isoformat(),
             "label": first.strftime("%m-%d %H:%M") if grain == "hour" else first.strftime("%m-%d")}
            for first, last in resource_period_bounds(start, end, "day" if grain == "shift" else grain)]


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


def _inside_window(start, end, scope):
    if local_time(start) < local_time(scope["range_start"]) or local_time(end) > local_time(scope["range_end"]):
        reject("invalid_input", "资源显示或查看时段须位于完整比较窗口内。", 422)


def _interval_scope(start, end, basis):
    return {"start": start, "end": end, "basis": basis}


def _continuations(periods, buckets):
    """Link a later date to its original night period, without measuring it twice."""
    notes = []
    for row in periods:
        if row["placeholder"] is not None:
            continue
        for bucket in buckets:
            if row["group_key"] != bucket["key"] and row["start"] < bucket["end"] and row["end"] > bucket["start"]:
                notes.append({"group_key": bucket["key"], "bucket_key": row["bucket_key"], "date": row["date"],
                              "start": row["start"], "end": row["end"],
                              "continuation_start": max(row["start"], bucket["start"]),
                              "continuation_end": min(row["end"], bucket["end"]),
                              "basis": "continuation_of_archived_work_period"})
    return notes


def resource_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20,
                     heatmap_page: Union[int, str] = 1, heatmap_size: Union[int, str] = 14, all_rows=False):
    if source.selected_ref is None:
        reject("invalid_input", "请选择已产出的候选方案后查看资源影响。", 422)
    section, kind, ref = (filters[key] for key in ("section", "resource_kind", "resource_ref"))
    engine = source.resources
    engine.configure(filters["pressure_threshold"])
    selected_resource: Any = engine.resource(ref, kind) if ref is not None else None
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    start, end = source.scope["range_start"], source.scope["range_end"]
    grain = filters["grain"]
    focus_start, focus_end = filters["display_start"] or start, filters["display_end"] or end
    _inside_window(focus_start, focus_end, source.scope)
    if filters["bucket_start"] is not None:
        _inside_window(filters["bucket_start"], filters["bucket_end"], source.scope)
    filters = dict(filters)
    common = {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
              "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["artifact"].get("label")},
              "filters": filters, "coverage": {"before": engine.coverage("reference", details=True), "after": engine.coverage(source.selected_ref, details=True)},
              "metric_version": RESOURCE_METRIC_VERSION}
    if section == "resource-days":
        resource = selected_resource
        row = engine.pair(resource)
        if filters["bucket_start"] is not None:
            low, high = filters["bucket_start"], filters["bucket_end"]
            items = engine.periods(resource, grain=grain, start=low, end=high, details=True)
            if len(items) != 1:
                reject("invalid_input", "请选择一个完整资源时段后查看安排。", 422)
            summary = {key: items[0][key] for key in ("before", "after", "deltas")}
            total = 1
        else:
            if grain == "shift":
                periods = engine.period_facts(resource, grain=grain)
                total = len(periods)
                selected_periods = periods if all_rows else periods[offset:offset + size]
                items = engine.periods(resource, grain=grain, details=True) if all_rows else [
                    item for period in selected_periods for item in engine.periods(
                        resource, grain=grain, start=period["start"], end=period["end"], details=True)]
            else:
                periods = _buckets(start, end, grain)
                total = len(periods)
                selected_periods = periods if all_rows else periods[offset:offset + size]
                items = engine.periods(resource, grain=grain, start=selected_periods[0]["start"],
                                       end=selected_periods[-1]["end"], details=True) if selected_periods else []
            summary = {key: row[key] for key in ("before", "after", "deltas")}
        return {**common, "resource": {key: resource[key] for key in ("ref", "label", "kind")},
                "items": items, "summary": summary, "window_scope": _interval_scope(start, end, "full_resource_window"),
                "display_scope": _interval_scope(items[0]["start"], items[-1]["end"], "selected_resource_periods") if items else None,
                "page": {"number": page, "size": size, "total": total, "has_more": offset + size < total}}
    heatmap_page, heatmap_size = parse_page(heatmap_page), parse_page(heatmap_size)
    if heatmap_size not in (7, 14, 31):
        reject("invalid_input", "资源热力图每页请选择7、14或31个时段。", 422)
    buckets = _buckets(focus_start, focus_end, grain)
    bucket_offset = (heatmap_page - 1) * heatmap_size
    shown_buckets = buckets if all_rows else buckets[bucket_offset:bucket_offset + heatmap_size]
    if not shown_buckets:
        reject("invalid_input", "资源热力图页码超出当前时段范围，请重新选择。", 422)
    display_start, display_end = shown_buckets[0]["start"], shown_buckets[-1]["end"]
    pressure_start, pressure_end = (display_start, display_end) if grain == "hour" else (start, end)
    if grain == "hour":
        filters.update(display_start=display_start, display_end=display_end)
    rows = []
    for row in engine.rows(kind):
        if ref is not None and row["resource_ref"] != ref:
            continue
        resource = engine.resource(row["resource_ref"], kind)
        if grain == "hour":
            calendar = engine.resource_calendar(resource)
            pressure_window = engine.index(source.selected_ref).window(resource, calendar, start=pressure_start, end=pressure_end)
            daily_peak = pressure_window["daily_peak_utilization"]
        else:
            daily_peak = row["after"]["daily_peak_utilization"]
        row["filter_summary"] = engine.filter_summary(resource, grain=grain, start=pressure_start, end=pressure_end,
                                                      daily_peak=daily_peak)
        if _resource_matches(row, filters):
            rows.append(row)
    rows = _ordered(rows, filters["sort"], filters["order"])
    visible = rows if all_rows else rows[offset:offset + size]
    rankings = {"top_pressure": _ordered(rows, "after_peak_utilization", "desc")[:10],
                "top_increase": _ordered(rows, "utilization_delta", "desc")[:10], "limit": 10, "total": len(rows)}
    output_refs = {row["resource_ref"] for row in visible + rankings["top_pressure"] + rankings["top_increase"]}
    for row in rows:
        if row["resource_ref"] in output_refs:
            resource = engine.resource(row["resource_ref"], kind)
            row["drill"] = {"selected": engine.drill(source.selected_ref, resource), "reference": engine.drill("reference", resource)}
    shown_keys = {bucket["key"] for bucket in shown_buckets}
    heatmap_rows = []
    if not all_rows:
        for row in visible:
            resource = engine.resource(row["resource_ref"], kind)
            heatmap_rows.append({
                "resource_ref": row["resource_ref"], "resource_kind": kind, "label": row["label"],
                "cells": engine.periods(resource, grain=grain, start=pressure_start, end=pressure_end, group_keys=shown_keys),
                "continuations": _continuations(engine.period_facts(resource, grain=grain,
                    start=pressure_start, end=pressure_end), shown_buckets) if grain == "shift" else []})
    previous, selected = engine.summary("reference", kind), engine.summary(source.selected_ref, kind)
    summary_fields = DELTA_FIELDS + ("high_pressure_count", "zero_capacity_task_count", "conflict_resource_count", "unknown_day_resource_count", "balance_cv", "used_resource_count")
    return {**common, "items": visible, "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)},
            "filter_options": {"resources": [{key: row[key] for key in ("ref", "label", "kind")} for row in engine.resources if row["kind"] == kind]},
            "summary": {"before": previous, "after": selected, "deltas": resource_deltas(previous, selected, summary_fields)},
            "rankings": rankings,
            "pressure_scope": _interval_scope(pressure_start, pressure_end, "displayed_hours" if grain == "hour" else "full_resource_window"),
            "heatmap": {"grain": grain, "buckets": shown_buckets,
                        "window_scope": _interval_scope(start, end, "full_resource_window"),
                        "focus_scope": _interval_scope(focus_start, focus_end, "hour_focus" if grain == "hour" else "full_resource_window"),
                        "display_scope": _interval_scope(display_start, display_end, "displayed_periods"),
                        "page": {"number": heatmap_page, "size": heatmap_size, "total": len(buckets), "has_more": bucket_offset + heatmap_size < len(buckets)},
                        "items": heatmap_rows}}


def read_resource_details(conn, run_ref, section, *, selected_candidate_ref=None, comparison_mode="candidates", reference_candidate_ref=None,
                          range_start=None, range_end=None, resource_view="selected_batches", resource_kind="machine", resource_ref=None,
                          pressure_filter="all", sort="after_peak_utilization", order="desc", page: Union[int, str] = 1,
                          size: Union[int, str] = 20, heatmap_page: Union[int, str] = 1, heatmap_size: Union[int, str] = 14,
                          grain="day", pressure_threshold: Union[float, str] = 0.9, display_start=None, display_end=None, bucket_start=None, bucket_end=None):
    from .decision_source import DecisionSource
    if selected_candidate_ref is None:
        reject("invalid_input", "资源明细需要指定所选候选方案。", 422)
    filters = normalize_resource_filters(section, resource_kind=resource_kind, resource_ref=resource_ref,
                                         pressure_filter=pressure_filter, sort=sort, order=order, grain=grain, pressure_threshold=pressure_threshold,
                                         display_start=display_start, display_end=display_end, bucket_start=bucket_start, bucket_end=bucket_end)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, selected_candidate_ref=selected_candidate_ref, comparison_mode=comparison_mode,
                                reference_candidate_ref=reference_candidate_ref, range_start=range_start, range_end=range_end, resource_view=resource_view)
        data = resource_details(source, filters, page=page, size=size, heatmap_page=heatmap_page, heatmap_size=heatmap_size)
        return data, source.state()
