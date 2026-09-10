"""Allowlisted planned-delivery DTOs; missing evidence is never a zero delay."""

from __future__ import annotations

from datetime import date

from core.services.common.overdue_calculations import due_exclusive, parse_dt

from .zero_duration_evidence import overlaps


def task_intervals(rows):
    result = {}
    for row in rows:
        start, end = parse_dt(row["start_time"]), parse_dt(row["end_time"])
        valid = start is not None and end is not None and (start < end or (start == end and row.get("_point_work")))
        result[row["schedule_id"]] = (start, end) if valid else None
    return result


def selected_batch_keys(rows, intervals, scope):
    if scope.range_start is None:
        return sorted({row["batch_id"] for row in rows})
    start, end = parse_dt(scope.range_start), parse_dt(scope.range_end)
    keys = set()
    for row in rows:
        interval = intervals[row["schedule_id"]]
        if interval is None or overlaps(interval[0], interval[1], start, end):
            keys.add(row["batch_id"])
    return sorted(keys)


def _due_fields(raw):
    parsed = parse_dt(raw)
    if parsed is None:
        missing = raw is None or isinstance(raw, str) and not raw.strip()
        return None, None, "due_date_missing" if missing else "due_date_invalid"
    if parsed.date() == date.max:
        return parsed.date().isoformat(), None, "due_date_unspecified"
    return parsed.date().isoformat(), due_exclusive(parsed), None


def _text(value):
    return value if isinstance(value, str) and value.strip() else None


def project_delivery_batch(batch, batch_ref, rows, operations, intervals, incomplete, uncertain):
    schedule, finish, reasons = _schedule_completion(rows, operations, intervals, incomplete, uncertain)
    due_date, deadline, due_issue = _due_fields(batch["due_date"])
    if due_issue:
        reasons.append(due_issue)
    part_no, part_label = _text(batch["part_no"]), _text(batch["part_name"])
    # Batches.part_name is a stored business label, not an invitation to guess a
    # historical label from today's Parts master when the batch label is absent.
    if part_no is None or part_label is None:
        reasons.append("part_label_missing")
    completeness = "complete" if not reasons else "incomplete" if schedule["unscheduled_operation_count"] or incomplete else "unknown"
    return {"batch_ref": batch_ref, "batch_id": batch["batch_id"], "part_no": part_no, "part_label": part_label,
            **schedule, **_finish_fields(schedule["schedule_complete"], finish),
            **_delivery_risk(schedule["schedule_complete"], finish, deadline),
            "due_date": due_date, "delivery_deadline_exclusive": deadline.isoformat(timespec="seconds") if deadline else None,
            "completeness": completeness, "issues": sorted(set(reasons))}


def _schedule_completion(rows, operations, intervals, incomplete, uncertain):
    expected = {row["op_id"] for row in operations}
    scheduled = {row["op_id"] for row in rows}
    valid = [intervals[row["schedule_id"]] for row in rows if intervals[row["schedule_id"]] is not None]
    missing_count, invalid_count = len(expected - scheduled), len(rows) - len(valid)
    reasons = list(uncertain)
    reasons.extend(row["point_evidence_issue"] for row in rows if row.get("point_evidence_issue"))
    if missing_count:
        reasons.append("operations_unscheduled")
    if not expected:
        reasons.append("operations_missing")
    if invalid_count:
        reasons.append("schedule_time_invalid")
    if incomplete:
        reasons.append("saved_plan_incomplete")
    complete = bool(expected) and not reasons
    finish = max((value[1] for value in valid), default=None)
    return {"schedule_complete": complete, "operation_count": len(expected), "scheduled_operation_count": len(scheduled),
            "unscheduled_operation_count": missing_count, "task_count": len(rows),
            "invalid_task_count": invalid_count}, finish, reasons


def _finish_fields(complete, finish):
    value = finish.isoformat(timespec="seconds") if finish is not None else None
    return {"planned_finish": value if complete else None,
            "partial_planned_finish": None if complete else value}


def _delivery_risk(complete, finish, deadline):
    known, overdue, delay = False, None, None
    if complete and finish is not None and deadline is not None:
        known, overdue = True, finish >= deadline
        delay = max(0.0, (finish - deadline).total_seconds())
    return {"risk": "overdue" if overdue else "on_time" if known else "unknown", "is_overdue": overdue,
            "delay_hours": round(delay / 3600.0, 2) if delay is not None else None,
            "delay_days": round(delay / 86400.0, 2) if delay is not None else None}
