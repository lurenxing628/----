"""Resource wall-clock occupancy; calendar capacity is never a shared scalar."""

from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, List, Mapping, Optional, Tuple, TypedDict

from core.services.capacity.plan_calendar_intervals import union
from core.services.capacity.plan_calendar_windows import available_intervals
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics
from core.shared.local_datetime import row_interval

from .calculation_helpers import is_internal_source


class _ResourceGroup(TypedDict):
    """One resource's clipped intervals keyed per operation, plus its task count and last seen label."""

    operations: DefaultDict[Any, List[Tuple[datetime, datetime]]]
    task_count: int
    label: Any


def utilization_from_groups(groups, *, start_dt, end_dt_excl, calendars, degradation_collector):
    result = {"machine": [], "operator": []}
    for (kind, key), item in groups.items():
        row = _utilization_row(kind, key, item, calendars[kind, key], start_dt, end_dt_excl)
        result[kind].append(row)
        if row["available_hours"] is None:
            degradation_collector.add(code="resource_load_capacity_failed", scope="report.utilization",
                field="可用工时", message="资源日历资料不完整，占用率无法计算。")
    for kind in result:
        result[kind].sort(key=lambda row: (row["hours"] is None, -(row["hours"] or 0.0), row[kind + "_id"]))
    return result["machine"], result["operator"]


def group_utilization_rows(schedule_rows, start, end):
    """Clip internal rows to the window and group their intervals per resource, then per operation."""
    groups: DefaultDict[Tuple[str, str], _ResourceGroup] = defaultdict(
        lambda: {"operations": defaultdict(list), "task_count": 0, "label": None})
    for row in schedule_rows:
        interval = clipped_occupancy(row, start, end)
        if interval is None:
            continue
        for kind in ("machine", "operator"):
            key = row[kind + "_id"]
            if key is None:
                continue
            item = groups[kind, key]
            # Multiple fragments of one operation do not become simultaneous jobs.
            item["operations"][row["op_id"]].append(interval)
            item["task_count"] += 1
            item["label"] = row[kind + "_name"]
    return groups


def _utilization_row(kind, key, item: _ResourceGroup, calendar, start, end):
    """One report row: a resource's unioned occupancy measured against its own calendar."""
    available = available_intervals(calendar)
    intervals = [span for values in item["operations"].values() for span in union(values)]
    metrics = ResourceUtilizationMetrics.from_normalized_availability(intervals, available).window(start, end)
    return {kind + "_id": key, kind + "_name": item["label"], "task_count": item["task_count"], **metrics,
            "hours": metrics["occupied_hours"], "capacity_hours": metrics["available_hours"],
            "utilization": metrics["utilization_ratio"], "calendar_issues": calendar["issues"]}


def utilization_percent(value: Optional[float]) -> Optional[float]:
    return round(value * 100.0, 2) if value is not None else None


def utilization_availability_note(row: Mapping[str, Any]) -> str:
    reason = row["reason"]
    if reason == "zero_available_capacity":
        return "此范围无可用工时"
    if reason == "calendar_unavailable":
        return "；".join(issue["message"] for issue in row["calendar_issues"]) or "日历资料不完整"
    return ""


def clipped_occupancy(row, start, end):
    """One internal row's positive occupancy clipped to [start, end); None when it occupies nothing there.

    Other sources, point events and rows outside the window occupy nothing.
    """
    if not is_internal_source(row["source"]) or row["is_point_event"]:
        return None
    row_start, row_end = row_interval(row)
    low, high = max(row_start, start), min(row_end, end)
    return (low, high) if low < high else None
