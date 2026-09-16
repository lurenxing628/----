"""Resource wall-clock occupancy; calendar capacity is never a shared scalar."""

from collections import defaultdict

from core.services.workbench.plan_calendar_intervals import union
from core.services.workbench.plan_calendar_windows import available_intervals
from core.services.workbench.resource_utilization_metrics import ResourceUtilizationMetrics

from .calculation_helpers import is_internal_source, is_valid_interval, parse_dt
from .report_degradation import record_report_bad_time_row, record_report_zero_capacity_window


def compute_utilization(*, schedule_rows, start_dt, end_dt_excl, calendars, degradation_collector=None):
    groups = defaultdict(lambda: {"operations": defaultdict(list), "task_count": 0, "label": None})
    for index, row in enumerate(schedule_rows):
        interval = _row_interval(row, start_dt, end_dt_excl, degradation_collector)
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
    result = {"machine": [], "operator": []}
    zero = {"machine": 0, "operator": 0}
    for (kind, key), item in groups.items():
        calendar = calendars.get((kind, key))
        available = available_intervals(calendar) if calendar is not None else None
        intervals = [span for values in item["operations"].values() for span in union(values)]
        metrics = ResourceUtilizationMetrics(intervals, available).window(start_dt, end_dt_excl)
        row = {kind + "_id": key, kind + "_name": item["label"], "task_count": item["task_count"], **metrics,
               "hours": metrics["occupied_hours"], "capacity_hours": metrics["available_hours"],
               "utilization": metrics["utilization_ratio"], "calendar_issues": calendar["issues"] if calendar else []}
        result[kind].append(row)
        zero[kind] += metrics["available_hours"] == 0
        if metrics["available_hours"] is None and degradation_collector is not None:
            degradation_collector.add(code="resource_load_capacity_failed", scope="report.utilization",
                field="可用工时", message="资源日历资料不完整，占用率无法计算。", sample=kind + "=" + key)
    record_report_zero_capacity_window(degradation_collector, scope="report.utilization",
                                      machine_row_count=zero["machine"], operator_row_count=zero["operator"])
    for kind in result:
        result[kind].sort(key=lambda row: (row["hours"] is None, -(row["hours"] or 0.0), row[kind + "_id"]))
    return result["machine"], result["operator"]


def _row_interval(row, start, end, collector):
    if not is_internal_source(row.get("source")):
        return None
    low, high = parse_dt(row.get("start_time")), parse_dt(row.get("end_time"))
    if not low or not high or not is_valid_interval(low, high):
        record_report_bad_time_row(collector, scope="report.utilization.schedule", row=row)
        return None
    low, high = max(low, start), min(high, end)
    return (low, high) if low < high else None
