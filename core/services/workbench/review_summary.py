"""Statistics over one immutable operation cohort; unknown hours stay null."""

from __future__ import annotations

import math
from collections import Counter
from statistics import median

from .review_values import hour_totals


def _completion_summary(operations):
    due = [row for row in operations if row["due"]]
    complete = [row for row in due if row["complete"]]
    on_time = [row for row in complete if row["finish_deviation_minutes"] is not None and row["finish_deviation_minutes"] <= 10]
    return {"due": len(due), "confirmed_due": len(complete), "due_on_time": len(on_time),
            "completion_rate": len(complete) / len(due) if due else None,
            "on_time_rate": len(on_time) / len(due) if due else None}


def _deviation_summary(operations):
    deviations = sorted(row["finish_deviation_minutes"] for row in operations if row["finish_deviation_minutes"] is not None)
    return {"median_finish_minutes": median(deviations) if deviations else None,
            "p90_finish_minutes": deviations[max(0, math.ceil(len(deviations) * .9) - 1)] if deviations else None,
            "finish_sample": len(deviations), "tolerance_minutes": 10}


def summary(operations, records):
    return {"operations": len(operations), "events": sum(row["record_kind"] == "legacy_event" for row in records),
            "production_reports": sum(row["record_kind"] == "production_report" for row in records), "records": len(records),
            **_completion_summary(operations), **_deviation_summary(operations),
            "unclosed_due": sum(row["unclosed"] for row in operations),
            "late_open": sum(row["late_open"] for row in operations), "finish_late": sum(row["finish_late"] for row in operations),
            "unreported": sum(row["execution_state"] == "unreported" for row in operations),
            "reported_operations": sum(row["record_count"] > 0 for row in operations),
            **hour_totals(records)}


def resource_rows(records, kind):
    groups = {}
    for event in records:
        key = event[kind + "_ref"]
        group = groups.setdefault(key, {"resource_ref": key, "resource_label": event[kind + "_label"],
            "operations": set(), "batches": set(), "events": 0, "production_reports": 0, "records": []})
        group["operations"].add(event["operation_ref"])
        group["batches"].add(event["batch_ref"])
        group["events"] += event["record_kind"] == "legacy_event"
        group["production_reports"] += event["record_kind"] == "production_report"
        group["records"].append(event)
    return [{**group, "operations": len(group["operations"]), "batches": len(group["batches"]),
             **hour_totals(group["records"]), "records": len(group["records"])} for group in groups.values()]


def _trend(operations, as_of):
    planned = Counter(row["planned_end"][:10] for row in operations if row["planned_end"])
    actual = Counter(row["confirmed_finish"][:10] for row in operations if row["confirmed_finish"])
    planned_count, actual_count, result = 0, 0, []
    for day in sorted(set(planned) | set(actual)):
        planned_count += planned[day]
        actual_count += actual[day]
        result.append({"date": day, "planned": planned_count, "actual": actual_count if day <= as_of[:10] else None})
    return result


def charts(operations, as_of):
    completed = [row for row in operations if row["finish_deviation_minutes"] is not None]
    finish = [{"label": label, "count": sum(test(row["finish_deviation_minutes"]) for row in completed)} for label, test in (
        ("提前超过10分钟", lambda value: value < -10), ("按时（偏差不超过10分钟）", lambda value: -10 <= value <= 10),
        ("晚完超过10分钟", lambda value: value > 10))]
    aging = [{"label": label, "count": sum(test(row["elapsed_since_planned_minutes"]) for row in operations if row["unclosed"])} for label, test in (
        ("到期10分钟内", lambda value: value <= 10), ("超过10分钟至1小时", lambda value: 10 < value <= 60),
        ("超过1小时至1天", lambda value: 60 < value <= 1440), ("超过1天", lambda value: value > 1440))]
    return {"finish": finish, "aging": aging, "trend": _trend(operations, as_of)}
