"""Represent only verified ledger intervals in the single-row scheduler contract."""

from core.infrastructure.errors import AppError, ErrorCode
from core.models.operation_execution_event import parse_operation_event_time

_STATUSES = {"unreported": "not_started", "started": "processing", "partial": "processing",
             "paused": "paused", "exception": "exception", "complete": "completed"}
_IDENTITY_GAPS = {"invalid_legacy_sequence", "legacy_identity_unresolved", "operation_retired"}


def _actual_time(value):
    return None if value is None else parse_operation_event_time(value)


def _resource_id(refs, resources, kind, reasons):
    refs = set(refs)
    if None in refs or len(refs) != 1:
        reasons.append("execution_ledger_actual_resource_missing_or_multiple")
        return None
    resource = resources.get(next(iter(refs)))
    if not resource or resource["kind"] != kind or not resource["available"]:
        reasons.append("execution_ledger_actual_resource_unavailable")
        return None
    return resource["business_code"]


def _actual_intervals(projection, reasons):
    intervals = []
    for report in projection.reports:
        start, end = _actual_time(report.actual_start), _actual_time(report.actual_end)
        if start is None or end is None or end <= start:
            reasons.append("execution_ledger_actual_interval_missing")
        else:
            intervals.append((start, end))
    if projection.completion_basis == "legacy_finish_event":
        start, end = _actual_time(projection.first_actual_start), _actual_time(projection.confirmed_finish)
        if start is not None and end is not None and end > start:
            intervals.append((start, end))
        else:
            reasons.append("execution_ledger_actual_interval_missing")
    return tuple(sorted(set(intervals)))


def _requires_ledger_projection(fact, projection):
    gap_codes = [gap["code"] for gap in projection.data_gaps]
    identity_invalid = bool(_IDENTITY_GAPS.intersection(gap_codes))
    # Existing event-only flows retain their scope, revision and duration contract.
    # A proven old finish must still protect completion after a version change.
    old_finish = projection.completion_basis == "legacy_finish_event" and fact.actual_status != "completed"
    return bool(projection.reports or identity_invalid or old_finish)


def _protected_status(projection, reasons):
    gap_codes = [gap["code"] for gap in projection.data_gaps]
    status = _STATUSES.get(projection.execution_state)
    if status is None:
        reasons.append("execution_ledger_protection_flags_missing")
        status = "exception"
    if projection.data_quality == "invalid":
        reasons.extend(gap_codes)
    if projection.reports and not projection.records_complete:
        reasons.extend(gap_codes or ["execution_ledger_report_fields_missing"])
    if status != "completed":
        # AJ currently exposes no verified remaining plan. Never use a plan tail,
        # quantity ratio, or zero duration as a substitute for that contract.
        reasons.append("execution_ledger_remaining_plan_unavailable")
    return status


def _protected_intervals(projection, status, reasons):
    intervals = _actual_intervals(projection, reasons)
    if status == "completed" and (not intervals or any(
        left[1] != right[0] for left, right in zip(intervals, intervals[1:])
    )):
        reasons.append("execution_ledger_intervals_not_representable")
    return intervals


def ledger_fact_changes(fact, projection, resources):
    if not _requires_ledger_projection(fact, projection):
        return None
    reasons = []
    status = _protected_status(projection, reasons)
    intervals = _protected_intervals(projection, status, reasons)
    evidence = [report.to_dict() for report in projection.reports] + projection.legacy_facts
    machine = _resource_id([row["actual_machine_ref"] for row in evidence], resources, "machine", reasons)
    operator = _resource_id([row["actual_operator_ref"] for row in evidence], resources, "operator", reasons)
    return {"actual_status": status, "actual_start_time": _actual_time(projection.first_actual_start),
            "actual_end_time": _actual_time(projection.confirmed_finish), "actual_machine_id": machine,
            "actual_operator_id": operator, "ledger_operation_ref": projection.operation_ref,
            "ledger_execution_state": projection.execution_state, "remaining_quantity": projection.remaining_quantity,
            "execution_effective_intervals": intervals, "execution_protection_reasons": tuple(dict.fromkeys(reasons))}


def ensure_ledger_execution_schedulable(facts):
    for op_id, fact in sorted(facts.items()):
        if fact.ledger_operation_ref is None:
            continue
        reasons = list(fact.execution_protection_reasons)
        if fact.ledger_execution_state not in _STATUSES:
            reasons.append("execution_ledger_protection_flags_missing")
        elif fact.actual_status != _STATUSES[fact.ledger_execution_state]:
            reasons.append("execution_ledger_protection_flags_inconsistent")
        if fact.ledger_execution_state in ("started", "partial", "paused", "exception"):
            reasons.append("execution_ledger_remaining_plan_unavailable")
        if fact.actual_status == "completed":
            intervals = fact.execution_effective_intervals
            if not intervals or fact.actual_start_time is None or fact.actual_end_time is None:
                reasons.append("execution_ledger_actual_interval_missing")
            elif fact.actual_start_time != intervals[0][0] or fact.actual_end_time != intervals[-1][1]:
                reasons.append("execution_ledger_actual_interval_inconsistent")
        if reasons:
            raise AppError(ErrorCode.SCHEDULE_CONFLICT,
                           "工序已有真实报工，但执行资料或剩余安排尚不能安全用于重排。请先补齐或核对报工；本次没有写入排程。",
                           details={"reason": "execution_ledger_requires_reconciliation", "op_id": op_id,
                                    "execution_state": fact.ledger_execution_state,
                                    "data_gaps": list(dict.fromkeys(reasons)), "remaining_quantity": fact.remaining_quantity})
