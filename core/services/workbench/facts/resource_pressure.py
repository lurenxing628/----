"""Daily pressure over an explicit local range, reusing calendar interval algebra."""

from datetime import timedelta

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import local_time

from .resource_projection import ResourceTaskIndex, resource_summary

MAX_DAYS = 3660
MAX_RESOURCE_DAYS = 40000


def range_days(start, end):
    low, high = local_time(start), local_time(end)
    if low > high:
        raise WorkbenchCommandRejected("invalid_input", "时间范围结束不能早于开始。", 422)
    last = (high - timedelta(microseconds=1)).date() if low < high else low.date()
    return low, high, (last - low.date()).days + 1


def _legacy_day(row):
    """Keep wall-clock aliases; the namespace exposes the canonical capacity fields."""
    return {"date": row["date"], "start": row["start"], "end": row["end"],
            "available_hours": row["available_hours"], "occupied_hours": row["span_occupied_hours"],
            "inside_available_hours": row["occupied_hours"], "outside_available_hours": row["outside_calendar_hours"],
            "overlap_hours": row["overlap_span_hours"], "utilization": row["utilization_ratio"],
            "reason": row["issues"][0]["code"] if row["issues"] else None, "window_metrics": row}


def pressure_from_index(index, resource, calendar, *, include_days=True):
    """Adapt the common result to the established daily-pressure read protocol."""
    window = index.window(resource, calendar)
    state = {"complete": "available", "not_applicable": "available", "partial": "partial", "unavailable": "unavailable"}[window["state"]]
    return {"state": state, "days": [_legacy_day(row) for row in index.days(resource, calendar)] if include_days else [],
            "peak_utilization": window["peak_utilization"],
            "reason": window["issues"][0]["code"] if window["issues"] else None,
            "zero_capacity_days": window["zero_capacity_days"], "unknown_days": window["unknown_days"],
            "window_metrics": window}


def daily_resource_pressure(tasks, calendar, start, end, *, resource, source="current_transaction_snapshot", work_available=True):
    return pressure_from_index(ResourceTaskIndex(tasks, start, end, source=source, work_available=work_available), resource, calendar)


def pressure_summary(resources):
    windows = [row["window_metrics"] for row in resources]
    summary = resource_summary(windows)
    return {"threshold": 0.9, "count": summary["high_pressure_count"], "known_count": summary["known_high_pressure_count"],
            "unknown_resources": summary["unknown_day_resource_count"], "zero_capacity_resources": sum(
                row["available_hours"] == 0 for row in windows),
            "resource_count": len(resources), "basis": "same_range_daily_peak_available_occupancy"}
