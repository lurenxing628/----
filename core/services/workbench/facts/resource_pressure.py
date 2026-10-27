"""Daily pressure over an explicit local range, reusing calendar interval algebra."""

from .resource_projection import resource_summary


def pressure_from_index(index, resource, calendar, *, include_days=True):
    """Adapt the common result to the daily-pressure read protocol; each day is the canonical window row."""
    window, days = index.window_with_days(resource, calendar) if include_days else (index.window(resource, calendar), [])
    state = {"complete": "available", "not_applicable": "available", "partial": "partial", "unavailable": "unavailable"}[window["state"]]
    return {"state": state, "days": days,
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
