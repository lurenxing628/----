"""Allowlisted planned-delivery DTOs; missing evidence is never a zero delay."""

from __future__ import annotations

from datetime import date

from core.models.enums import DeliveryCompletionState, DeliveryRisk, DueState
from core.services.common.overdue_calculations import due_exclusive, parse_dt
from core.services.workbench.facts.zero_duration_evidence import overlaps


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
        return None, None, DueState.INVALID.value, "due_date_missing" if missing else "due_date_invalid"
    if parsed.date() == date.max:
        return parsed.date().isoformat(), None, DueState.UNSPECIFIED.value, None
    return parsed.date().isoformat(), due_exclusive(parsed), DueState.SPECIFIED.value, None


def _text(value):
    return value if isinstance(value, str) and value.strip() else None


def project_delivery_batch(batch, batch_ref, rows, operations, intervals, incomplete, uncertain, *, deferred_operation_ids=()):
    schedule, finish, reasons = _schedule_completion(rows, operations, intervals, incomplete, uncertain, deferred_operation_ids)
    due_date, deadline, due_state, due_issue = _due_fields(batch["due_date"])
    if due_issue:
        reasons.append(due_issue)
    part_no, part_label = _text(batch["part_no"]), _text(batch["part_name"])
    # Batches.part_name is a stored business label, not an invitation to guess a
    # historical label from today's Parts master when the batch label is absent.
    if part_no is None or part_label is None:
        reasons.append("part_label_missing")
    completeness = ("incomplete" if schedule["completion_state"] == DeliveryCompletionState.DEFERRED.value
                    else schedule["completion_state"])
    quantity = batch.get("quantity")
    return {"batch_ref": batch_ref, "batch_id": batch["batch_id"], "part_no": part_no, "part_label": part_label,
            "priority": _text(batch.get("priority")),
            "quantity": quantity if type(quantity) is int and quantity >= 0 else None,
            **schedule, **_finish_fields(schedule["schedule_complete"], finish),
            **_delivery_risk(schedule["schedule_complete"], finish, deadline, due_state),
            "due_date": due_date, "due_state": due_state, "due_issue": due_issue,
            "delivery_deadline_exclusive": deadline.isoformat(timespec="seconds") if deadline else None,
            "completeness": completeness, "issues": sorted(set(reasons))}


def _schedule_completion(rows, operations, intervals, incomplete, uncertain, deferred_operation_ids):
    expected = {row["op_id"] for row in operations}
    scheduled = {row["op_id"] for row in rows}
    valid = [intervals[row["schedule_id"]] for row in rows if intervals[row["schedule_id"]] is not None]
    missing = expected - scheduled
    deferred = missing & set(deferred_operation_ids)
    ordinary_missing = missing - deferred
    missing_count, invalid_count = len(missing), len(rows) - len(valid)
    reasons = list(uncertain)
    point_issues = [row["point_evidence_issue"] for row in rows if row.get("point_evidence_issue")]
    reasons.extend(point_issues)
    if ordinary_missing:
        reasons.append("operations_unscheduled")
    if deferred:
        reasons.append("material_deferred")
    if not expected:
        reasons.append("operations_missing")
    if invalid_count:
        reasons.append("schedule_time_invalid")
    if incomplete and not (deferred and not ordinary_missing):
        reasons.append("saved_plan_incomplete")
    complete = bool(expected) and not reasons
    if complete:
        state = DeliveryCompletionState.COMPLETE.value
    elif deferred and not ordinary_missing and not invalid_count and not uncertain and not point_issues:
        state = DeliveryCompletionState.DEFERRED.value
    elif ordinary_missing or incomplete:
        state = DeliveryCompletionState.INCOMPLETE.value
    else:
        state = DeliveryCompletionState.UNKNOWN.value
    finish = max((value[1] for value in valid), default=None)
    return {"schedule_complete": complete, "operation_count": len(expected), "scheduled_operation_count": len(scheduled),
            "unscheduled_operation_count": missing_count, "task_count": len(rows),
            "invalid_task_count": invalid_count, "completion_state": state,
            "deferred_operation_count": len(deferred),
            "ordinary_unscheduled_operation_count": len(ordinary_missing)}, finish, reasons


def _finish_fields(complete, finish):
    value = finish.isoformat() if finish is not None else None
    return {"planned_finish": value if complete else None,
            "partial_planned_finish": None if complete else value}


def _delivery_risk(complete, finish, deadline, due_state):
    known, overdue, delay = False, None, None
    if complete and finish is not None and deadline is not None:
        known, overdue = True, finish >= deadline
        delay = max(0.0, (finish - deadline).total_seconds())
    risk = (DeliveryRisk.NOT_APPLICABLE.value if due_state == DueState.UNSPECIFIED.value
            else DeliveryRisk.OVERDUE.value if overdue else DeliveryRisk.ON_TIME.value if known else DeliveryRisk.UNKNOWN.value)
    return {"risk": risk, "is_overdue": overdue,
            "delay_hours": delay / 3600.0 if delay is not None else None,
            "delay_days": delay / 86400.0 if delay is not None else None}


def delivery_summary(items, missing_count=0):
    """Whole-chain and due coverage; invalid due values remain unknown evidence.

    Eligible means a specified due date. Evaluation also includes invalid due
    evidence, so invalid-only ranges never become not applicable. Unspecified
    dates have no tardiness value and are excluded from both sets.
    """
    eligible = [row for row in items if row["due_state"] == DueState.SPECIFIED.value]
    excluded = sum(row["due_state"] == DueState.UNSPECIFIED.value for row in items)
    invalid = sum(row["due_state"] == DueState.INVALID.value for row in items) + missing_count
    known = [row for row in eligible if row["risk"] in (DeliveryRisk.ON_TIME.value, DeliveryRisk.OVERDUE.value)]
    evaluated = len(eligible) + invalid
    unknown = evaluated - len(known)
    state = ("not_applicable" if not evaluated else "complete" if not unknown
             else "partial" if known else "unavailable")
    overdue = sum(row["is_overdue"] is True for row in known)
    tardiness = sum(row["delay_hours"] for row in known)
    complete_refs = sorted(row["batch_ref"] for row in items if row["schedule_complete"])
    deferred_refs = sorted(row["batch_ref"] for row in items if row["completion_state"] == DeliveryCompletionState.DEFERRED.value)
    batch_count = len(items) + missing_count
    return {"state": state, "batch_count": batch_count, "due_eligible_count": len(eligible),
            "excluded_due_count": excluded, "invalid_due_count": invalid, "due_evaluation_count": evaluated,
            "known_due_count": len(known), "unknown_due_count": unknown, "unknown_count": unknown,
            "overdue_count": overdue if state == "complete" else None, "known_overdue_count": overdue,
            "total_tardiness_hours": tardiness if state == "complete" else None,
            "known_tardiness_hours": tardiness if evaluated else None,
            "on_time_count": len(known) - overdue if state == "complete" else None,
            "known_on_time_count": len(known) - overdue,
            "complete_batch_count": len(complete_refs), "incomplete_batch_count": batch_count - len(complete_refs),
            "deferred_batch_count": len(deferred_refs), "complete_batch_refs": complete_refs,
            "deferred_batch_refs": deferred_refs,
            "known_batch_refs": sorted(row["batch_ref"] for row in known),
            "unknown_batch_refs": sorted(row["batch_ref"] for row in items if row["risk"] == DeliveryRisk.UNKNOWN.value)}


def delivery_batch_delta(before, after):
    """Selected minus reference over the shared whole-batch delivery facts."""
    first, second = before["delay_hours"], after["delay_hours"]
    delay = None if first is None or second is None else second - first
    old_finish, new_finish = parse_dt(before["planned_finish"]), parse_dt(after["planned_finish"])
    finish = None if old_finish is None or new_finish is None else (new_finish - old_finish).total_seconds() / 3600.0
    kinds = []
    if finish is not None and finish != 0:
        kinds.append("earlier" if finish < 0 else "later")
    if before["is_overdue"] is not None and after["is_overdue"] is not None:
        if after["is_overdue"] and not before["is_overdue"]:
            kinds.append("new_overdue")
        elif before["is_overdue"] and not after["is_overdue"]:
            kinds.append("relieved_overdue")
    completion_known = (before["completion_state"] != DeliveryCompletionState.UNKNOWN.value
                        and after["completion_state"] != DeliveryCompletionState.UNKNOWN.value)
    if completion_known and before["schedule_complete"] != after["schedule_complete"]:
        kinds.append("completion_improved" if after["schedule_complete"] else "completion_worsened")
    if not kinds:
        kinds.append("unknown" if finish is None or before["due_state"] == DueState.INVALID.value
                     or after["due_state"] == DueState.INVALID.value else "unchanged")
    return {"finish_delta_hours": finish, "delay_delta_hours": delay, "change_kinds": kinds}
