"""Daily pressure over an explicit local range, reusing calendar interval algebra."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import local_time

from .plan_calendar_intervals import IntervalIndex, intersection, segments, union
from .plan_calendar_windows import available_intervals

MAX_DAYS = 3660
MAX_RESOURCE_DAYS = 40000


def range_days(start, end):
    low, high = local_time(start), local_time(end)
    if low > high:
        raise WorkbenchCommandRejected("invalid_input", "时间范围结束不能早于开始。", 422)
    last = (high - timedelta(microseconds=1)).date() if low < high else low.date()
    return low, high, (last - low.date()).days + 1


def _days(low, high):
    if low == high:
        yield low, high
    while low < high:
        boundary = high if low.date() == date.max else datetime.combine(low.date() + timedelta(days=1), time.min)
        end = min(high, boundary)
        yield low, end
        low = end


def _occupied(tasks, low, high):
    operations = defaultdict(list)
    for task in tasks:
        start, end = local_time(task["start"]), local_time(task["end"])
        if start > end:
            raise WorkbenchCommandRejected("invalid_task_interval", "这条任务的时间填得不对，系统不会另算一个占用值。", 422)
        if start == end:
            continue
        if start < high and end > low:
            operations[task["operation_ref"]].append((max(start, low), min(end, high)))
    intervals = [value for values in operations.values() for value in union(values)]
    overlap = [(start, end) for start, end, count in segments(intervals) if count > 1]
    return union(intervals), union(overlap)


def _day_pressure(first, last, occupied, overlap, available, inside_available):
    amount = available.hours_between(first, last) if available is not None else None
    used = occupied.hours_between(first, last)
    inside = inside_available.hours_between(first, last) if inside_available is not None else None
    utilization = inside / amount if inside is not None and amount is not None and amount > 0 else None
    reason = "calendar_unavailable" if amount is None else "zero_available_capacity" if amount == 0 else None
    return {"date": first.date().isoformat(), "start": first.isoformat(), "end": last.isoformat(),
            "available_hours": None if amount is None else round(amount, 6), "occupied_hours": round(used, 6),
            "inside_available_hours": None if inside is None else round(inside, 6),
            "outside_available_hours": None if inside is None else round(max(0.0, used - inside), 6),
            "overlap_hours": round(overlap.hours_between(first, last), 6),
            "utilization": None if utilization is None else round(utilization, 6), "reason": reason}


def _pressure_totals(days):
    known = [row["utilization"] for row in days if row["utilization"] is not None]
    unknown = sum(row["available_hours"] is None for row in days)
    return {"state": "unavailable" if unknown else "available", "days": days,
            "peak_utilization": None if unknown or not known else max(known),
            "reason": "calendar_unavailable" if unknown else "zero_available_capacity" if not known else None,
            "zero_capacity_days": sum(row["available_hours"] == 0 for row in days), "unknown_days": unknown}


def daily_resource_pressure(tasks, calendar, start, end):
    low, high, day_count = range_days(start, end)
    if day_count > MAX_DAYS:
        return {"state": "unavailable", "days": [], "peak_utilization": None,
                "reason": "calendar_range_limit", "zero_capacity_days": 0, "unknown_days": day_count}
    occupied, overlap = _occupied(tasks, low, high)
    occupied_index, overlap_index = IntervalIndex(occupied), IntervalIndex(overlap)
    available = available_intervals(calendar) if calendar is not None else None
    available_index = IntervalIndex(available) if available is not None else None
    inside_index = IntervalIndex(intersection(occupied, available)) if available is not None else None
    days = [_day_pressure(first, last, occupied_index, overlap_index, available_index, inside_index)
            for first, last in _days(low, high)]
    return _pressure_totals(days)


def pressure_summary(resources):
    known = sum(row["peak_utilization"] is not None and row["peak_utilization"] >= 0.9 for row in resources)
    unknown = sum(row["state"] != "available" for row in resources)
    return {"threshold": 0.9, "count": None if unknown else known, "known_count": known,
            "unknown_resources": unknown, "zero_capacity_resources": sum(
                row["state"] == "available" and row["peak_utilization"] is None for row in resources),
            "resource_count": len(resources), "basis": "same_range_daily_peak_available_occupancy"}
