"""Resource wall-clock occupancy; calendar capacity is never a shared scalar."""

from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, List, Mapping, Optional, Tuple, TypedDict

from core.services.capacity.plan_calendar_intervals import union
from core.services.capacity.plan_calendar_windows import available_intervals
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics
from core.shared.local_datetime import parse_local_datetime as parse_dt

from .calculation_helpers import is_internal_source
from .report_degradation import record_report_bad_time_row


class _ResourceGroup(TypedDict):
    """One resource's clipped intervals keyed per operation, plus its task count and last seen label."""

    operations: DefaultDict[Any, List[Tuple[datetime, datetime]]]
    task_count: int
    label: Any


def compute_utilization(*, schedule_rows, start_dt, end_dt_excl, calendars, degradation_collector):
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl, degradation_collector)
    return utilization_from_groups(
        groups,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        calendars=calendars,
        degradation_collector=degradation_collector,
    )


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


def group_utilization_rows(schedule_rows, start, end, collector):
    """Clip internal rows to the window and group their intervals per resource, then per operation."""
    groups: DefaultDict[Tuple[str, str], _ResourceGroup] = defaultdict(
        lambda: {"operations": defaultdict(list), "task_count": 0, "label": None})
    for row in schedule_rows:
        interval = row_interval(row, start, end, collector)
        if interval is None:
            continue
        for kind in ("machine", "operator"):
            raw_key = row.get(kind + "_id")
            if raw_key is None or not str(raw_key).strip():
                continue
            key = str(raw_key)
            item = groups[kind, key]
            # Multiple fragments of one operation do not become simultaneous jobs.
            item["operations"][row["op_id"]].append(interval)
            item["task_count"] += 1
            item["label"] = row.get(kind + "_name")
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


def row_interval(row, start, end, collector=None):
    """One internal row's positive occupancy clipped to [start, end); None when it occupies nothing there.

    Other sources, point events and rows outside the window occupy nothing, nor do rows whose
    times are unreadable or reversed. Resource calendars are sized from exactly these rows;
    only the utilization pass supplies its collector, so each bad row is reported once.
    """
    if not is_internal_source(row.get("source")):
        return None
    low, high = parse_dt(row.get("start_time")), parse_dt(row.get("end_time"))
    if not low or not high or high < low:
        if collector is not None:
            record_report_bad_time_row(collector, scope="report.utilization.schedule")
        return None
    if low == high:
        return None
    low, high = max(low, start), min(high, end)
    return (low, high) if low < high else None
