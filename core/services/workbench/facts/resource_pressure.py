"""Daily pressure over an explicit local range, reusing calendar interval algebra."""

from .resource_projection import resource_summary


def legacy_day(row):
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
    return {"state": state, "days": [legacy_day(row) for row in index.days(resource, calendar)] if include_days else [],
            "peak_utilization": window["peak_utilization"],
            "reason": window["issues"][0]["code"] if window["issues"] else None,
            "zero_capacity_days": window["zero_capacity_days"], "unknown_days": window["unknown_days"],
            "window_metrics": window}


def pressure_summary(resources):
    windows = [row["window_metrics"] for row in resources]
    summary = resource_summary(windows)
    return {"threshold": 0.9, "count": summary["high_pressure_count"], "known_count": summary["known_high_pressure_count"],
            "unknown_resources": summary["unknown_day_resource_count"], "zero_capacity_resources": sum(
                row["available_hours"] == 0 for row in windows),
            "resource_count": len(resources), "basis": "same_range_daily_peak_available_occupancy"}
