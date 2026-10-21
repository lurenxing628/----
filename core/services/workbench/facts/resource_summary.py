"""Whole-cohort totals from the shared resource windows, without a second clock."""

from math import fsum, sqrt
from typing import Any, Dict

HOUR_FIELDS = ("available_hours", "occupied_hours", "summed_load_hours", "outside_calendar_hours", "overlap_hours",
               "span_occupied_hours", "span_summed_hours", "span_overlap_hours", "overlap_span_hours")
FLAG_FIELDS = {"high_pressure_count": "high_pressure", "zero_capacity_task_count": "zero_capacity_task",
               "conflict_resource_count": "conflict"}


def _issues(items):
    result, seen = [], set()
    for item in items:
        value = {"code": item["code"], "message": item["message"]}
        if item.get("field") is not None:
            value["field"] = item["field"]
        key = (value["code"], value["message"], value.get("field"))
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def _work_complete(row):
    return row["work_available"] and row["work_state"] == "complete" and not row["unknown_workload_count"]


def _sum(values, *, empty=False):
    known = [value for value in values if value is not None]
    return fsum(known) if known or empty else None


def _count(values):
    known = sum(value is True for value in values)
    return (None if None in values else known), known


def _known(row, field, work_available=True):
    if field != "available_hours" and (not work_available or not row["work_available"]):
        return None
    return row["known_" + field] if "known_" + field in row else row[field]


def _full_window_pairs(rows):
    """Balance compares complete resource windows, including their idle capacity."""
    return [row for row in rows if _work_complete(row) and row["available_hours"] is not None
            and row["occupied_hours"] is not None]


def _known_day_totals(rows, field):
    """Ratio subtotals share the known calendar days; incomplete work stays excluded."""
    values = [(_known(row, field), _known(row, "available_hours")) for row in rows if _work_complete(row)]
    pairs = [(numerator, denominator) for numerator, denominator in values
             if numerator is not None and denominator is not None]
    return _sum([numerator for numerator, _ in pairs]), _sum([denominator for _, denominator in pairs])


def _ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def _balance(rows):
    positive = [row for row in rows if row["available_hours"] > 0]
    capacity = fsum(row["available_hours"] for row in positive)
    occupied = fsum(row["occupied_hours"] for row in positive)
    if not capacity:
        return None, "no_positive_capacity"
    mean = occupied / capacity
    if mean == 0:
        return None, "no_occupied_resources"
    variance = fsum(row["available_hours"] * (row["occupied_hours"] / row["available_hours"] - mean) ** 2
                    for row in positive) / capacity
    return sqrt(variance) / mean, None


def _balance_fields(rows, identity_unknown, work_available):
    pairs = _full_window_pairs(rows if work_available else [])
    known, reason = _balance(pairs)
    complete = work_available and not identity_unknown and all(row.get("available_hours") is not None
                and (row["available_hours"] == 0 or _work_complete(row) and row.get("occupied_hours") is not None)
                for row in rows)
    if not complete:
        state = "partial" if pairs else "unavailable"
        value = None
        reason_value = {"code": "resource_balance_incomplete", "message": "部分资源的完整容量或占用缺项，均衡度显示覆盖不足。"}
    else:
        state, value = ("complete", known) if known is not None else ("not_applicable", None)
        reasons = {"no_positive_capacity": "共同资源集合在此窗口没有正容量，均衡度不适用。",
                   "no_occupied_resources": "共同窗口内没有资源占用，均衡度不适用。"}
        reason_value = {"code": reason, "message": reasons[reason]} if reason else None
    return {"balance_cv": value, "known_balance_cv": known, "balance_state": state, "balance_reason": reason_value}


def resource_summary(windows, *, kind=None, identity_issues=(), work_available=True):
    """Sum complete facts and known lower bounds independently over a fixed cohort."""
    rows = [row for row in windows if kind is None or row["resource_kind"] == kind]
    identity = [item for item in identity_issues if kind is None or item.get("kind") in (None, kind)]
    workload_unknown = not work_available or bool(identity) or any(not _work_complete(row) for row in rows)
    result: Dict[str, Any] = {"resource_count": len(rows),
              "known_capacity_count": sum(row["available_hours"] is not None for row in rows),
              "unknown_capacity_count": sum(row["available_hours"] is None for row in rows),
              "unknown_workload_count": sum(row["unknown_workload_count"] for row in rows) + len(identity),
              "unknown_workload_resource_count": len(rows) if identity or not work_available else sum(not _work_complete(row) for row in rows)}
    for field in HOUR_FIELDS:
        values = [row[field] for row in rows]
        result[field] = None if (field != "available_hours" and workload_unknown) or None in values else fsum(values)
        result["known_" + field] = _sum([_known(row, field, work_available) for row in rows],
                                      empty=not rows and (field == "available_hours" or work_available and not identity))
    for field in ("task_count", "operation_count"):
        values = [row[field] for row in rows]
        result[field] = None if workload_unknown or None in values else sum(values)
        known_counts = [value for value in (_known(row, field, work_available) for row in rows)
                        if value is not None]
        result["known_" + field] = sum(known_counts) if known_counts or not rows and work_available and not identity else None
    used = [None if row["operation_count"] is None or not _work_complete(row) else row["operation_count"] > 0 for row in rows]
    result["used_resource_count"], _ = _count(used)
    if identity or not work_available:
        result["used_resource_count"] = None
    result["known_used_resource_count"] = sum((_known(row, "operation_count") or 0) > 0 for row in rows) if work_available else None
    for field, flag in FLAG_FIELDS.items():
        result[field], result["known_" + field] = _count([row[flag] for row in rows])
        if identity or not work_available:
            result[field] = None
        if not work_available:
            result["known_" + field] = None
    unknown_day_count = sum(row["unknown_days"] > 0 for row in rows)
    result["unknown_day_resource_count"] = result["known_unknown_day_resource_count"] = unknown_day_count
    peak_rows = [row for row in rows if row["available_hours"] != 0]
    peaks = [row["peak_utilization"] for row in peak_rows]
    known_peaks = [_known(row, "peak_utilization", work_available) for row in rows]
    peak_unknown = any(row["available_hours"] is None or not _work_complete(row) for row in peak_rows)
    result["peak_utilization"] = None if identity or not work_available or peak_unknown or None in peaks or not peaks else max(peaks)
    result["known_peak_utilization"] = max((value for value in known_peaks if value is not None), default=None)
    numerator, denominator = result["occupied_hours"], result["available_hours"]
    known_numerator, known_denominator = _known_day_totals(rows if work_available else [], "occupied_hours")
    known_load, known_load_capacity = _known_day_totals(rows if work_available else [], "summed_load_hours")
    result.update(numerator_hours=numerator, denominator_hours=denominator,
                  known_numerator_hours=known_numerator, known_denominator_hours=known_denominator,
                  utilization_ratio=_ratio(numerator, denominator), demand_ratio=_ratio(result["summed_load_hours"], denominator),
                  known_utilization_ratio=_ratio(known_numerator, known_denominator),
                  known_demand_ratio=_ratio(known_load, known_load_capacity))
    result.update(_balance_fields(rows, bool(identity), work_available))
    unknown = workload_unknown or result["unknown_capacity_count"] > 0 or any(row["state"] in ("partial", "unavailable") for row in rows)
    known = any(result["known_" + field] is not None for field in HOUR_FIELDS)
    result["state"] = ("unavailable" if identity or not work_available else "not_applicable") if not rows else (
        "complete" if not unknown else "partial" if known else "unavailable")
    result["issues"] = _issues([item for row in rows for item in row["issues"]] + identity)
    return result
