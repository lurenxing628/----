"""Resource detail pages over the decision resource engine: filters, ordering and heatmap pages."""

from math import isfinite
from typing import Any, Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.resource_calendar import resource_period_bounds
from core.services.workbench.facts.resource_projection import RESOURCE_METRIC_VERSION

from .decision_queries import parse_page
from .decision_resource_engine import DELTA_FIELDS, KINDS, resource_deltas

SORTS = ("after_utilization", "utilization_delta", "after_peak_utilization", "after_demand_hours", "after_available_hours", "label")
PRESSURE_FILTERS = ("all", "high_pressure", "demand_overload", "zero_capacity", "conflicts", "unknown")
GRAINS = ("hour", "day", "shift", "week")


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
