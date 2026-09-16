"""Resource wall-clock occupancy; calendar capacity is never a shared scalar."""

from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, List, Tuple, TypedDict

from core.services.capacity.plan_calendar_intervals import union
from core.services.capacity.plan_calendar_windows import available_intervals
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics

from .calculation_helpers import is_internal_source, is_valid_interval, parse_dt
from .report_degradation import record_report_bad_time_row, record_report_zero_capacity_window


class _ResourceGroup(TypedDict):
    """One resource's clipped intervals keyed per operation, plus its task count and last seen label."""

    operations: DefaultDict[Tuple[str, Any], List[Tuple[datetime, datetime]]]
    task_count: int
    label: Any


def compute_utilization(*, schedule_rows, start_dt, end_dt_excl, calendars, degradation_collector=None):
    groups = _group_operation_intervals(schedule_rows, start_dt, end_dt_excl, degradation_collector)
    result = {"machine": [], "operator": []}
    zero = {"machine": 0, "operator": 0}
    for (kind, key), item in groups.items():
        row = _utilization_row(kind, key, item, calendars.get((kind, key)), start_dt, end_dt_excl)
        result[kind].append(row)
        zero[kind] += row["available_hours"] == 0
        if row["available_hours"] is None and degradation_collector is not None:
            degradation_collector.add(code="resource_load_capacity_failed", scope="report.utilization",
                field="可用工时", message="资源日历资料不完整，占用率无法计算。", sample=kind + "=" + key)
    record_report_zero_capacity_window(degradation_collector, scope="report.utilization",
                                      machine_row_count=zero["machine"], operator_row_count=zero["operator"])
    for kind in result:
        result[kind].sort(key=lambda row: (row["hours"] is None, -(row["hours"] or 0.0), row[kind + "_id"]))
    return result["machine"], result["operator"]


def _group_operation_intervals(schedule_rows, start, end, collector):
    """Clip internal rows to the window and group their intervals per resource, then per operation."""
    groups: DefaultDict[Tuple[str, str], _ResourceGroup] = defaultdict(
        lambda: {"operations": defaultdict(list), "task_count": 0, "label": None})
    for index, row in enumerate(schedule_rows):
        interval = _row_interval(row, start, end, collector)
        if interval is None:
            continue
        for kind in ("machine", "operator"):
            key = str(row.get(kind + "_id") or "").strip()
            if not key:
                continue
            item = groups[kind, key]
            # Multiple fragments of one operation do not become simultaneous jobs.
            op = ("operation", row["op_id"]) if row.get("op_id") is not None else ("row", index)
            item["operations"][op].append(interval)
            item["task_count"] += 1
            item["label"] = row.get(kind + "_name")
    return groups


def _utilization_row(kind, key, item: _ResourceGroup, calendar, start, end):
    """One report row: a resource's unioned occupancy measured against its own calendar."""
    available = available_intervals(calendar) if calendar is not None else None
    intervals = [span for values in item["operations"].values() for span in union(values)]
    metrics = ResourceUtilizationMetrics(intervals, available).window(start, end)
    return {kind + "_id": key, kind + "_name": item["label"], "task_count": item["task_count"], **metrics,
            "hours": metrics["occupied_hours"], "capacity_hours": metrics["available_hours"],
            "utilization": metrics["utilization_ratio"], "calendar_issues": calendar["issues"] if calendar else []}


def _row_interval(row, start, end, collector):
    if not is_internal_source(row.get("source")):
        return None
    low, high = parse_dt(row.get("start_time")), parse_dt(row.get("end_time"))
    if not low or not high or not is_valid_interval(low, high):
        record_report_bad_time_row(collector, scope="report.utilization.schedule", row=row)
        return None
    low, high = max(low, start), min(high, end)
    return (low, high) if low < high else None
