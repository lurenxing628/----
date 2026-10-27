"""Preserve actual execution across plan versions."""

from datetime import datetime

from core.errors import AppError, ErrorCode
from core.models.enums import SourceType
from core.models.operation_execution_scope import parse_operation_event_time

_STATUSES = {"unreported": "not_started", "started": "processing", "partial": "processing",
             "complete": "completed"}


def is_point_work(source, setup_hours, unit_hours, target_quantity):
    values = (setup_hours, unit_hours, target_quantity)
    return (
        source == SourceType.INTERNAL.value
        and type(target_quantity) is int
        and all(
            type(value) in (int, float) and 0 <= value <= 9007199254740991
            for value in values
        )
        and setup_hours == 0
        and (unit_hours == 0 or target_quantity == 0)
    )


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


def _report_segments(projection):
    return sorted(
        ((_actual_time(report.actual_start), _actual_time(report.actual_end), report) for report in projection.reports),
        key=lambda segment: (segment[0] or datetime.min, segment[1] or datetime.min),
    )


def _actual_intervals(reasons, report_segments, *, is_point):
    intervals = []
    for start, end, report in report_segments:
        valid_point = is_point and end == start and report.effective_processing_hours == 0
        if start is None or end is None or (end <= start and not valid_point):
            reasons.append("execution_ledger_actual_interval_missing")
        else:
            intervals.append((start, end))
    return tuple(intervals)


def _protected_status(projection, reasons, gap_codes):
    status = _STATUSES.get(projection.execution_state)
    if status is None:
        reasons.append("execution_ledger_protection_flags_missing")
        status = "not_started"
    if projection.data_quality == "invalid":
        reasons.extend(gap_codes)
    if projection.reports and not projection.records_complete:
        reasons.extend(gap_codes or ["execution_ledger_report_fields_missing"])
    if status != "completed":
        # AJ currently exposes no verified remaining plan. Never use a plan tail,
        # quantity ratio, or zero duration as a substitute for that contract.
        reasons.append("execution_ledger_remaining_plan_unavailable")
    return status


def _occupancy_intervals(intervals):
    # Zero-duration point reports are evidence inside the actual span, not occupancy.
    positive = tuple(interval for interval in intervals if interval[0] < interval[1])
    return positive or intervals


def _protected_intervals(status, reasons, report_segments, *, is_point):
    intervals = _actual_intervals(reasons, report_segments, is_point=is_point)
    if status == "completed":
        span = _occupancy_intervals(intervals)
        if not span or any(left[1] != right[0] for left, right in zip(span, span[1:])) or any(
            start < span[0][0] or end > span[-1][1] for start, end in intervals
        ):
            reasons.append("execution_ledger_intervals_not_representable")
    return intervals


def _actual_resources(projection, resources, *, source, reasons, report_segments=()):
    machine, operator = None, None
    if source == SourceType.EXTERNAL.value:
        fields = ("actual_machine_ref", "actual_operator_ref")
        if any(getattr(report, field) is not None for report in projection.reports for field in fields):
            reasons.append("execution_ledger_external_resource_conflict")
    elif source == SourceType.INTERNAL.value:
        if projection.reports:
            primary = next(
                (seg[2] for seg in report_segments if seg[0] is not None and seg[1] is not None and seg[0] < seg[1]),
                report_segments[0][2],
            )
            resolved = {}
            for field, kind in (("actual_machine_ref", "machine"), ("actual_operator_ref", "operator")):
                refs = {getattr(report, field) for report in projection.reports}
                codes = {ref: _resource_id((ref,), resources, kind, reasons) for ref in refs}
                resolved[field] = codes[getattr(primary, field)]
            machine, operator = resolved["actual_machine_ref"], resolved["actual_operator_ref"]
        else:
            machine = _resource_id((), resources, "machine", reasons)
            operator = _resource_id((), resources, "operator", reasons)
    else:
        reasons.append("execution_ledger_operation_source_invalid")
    return machine, operator


def ledger_fact_changes(projection, resources, *, source, setup_hours, unit_hours):
    gap_codes = [gap["code"] for gap in projection.data_gaps]
    if not projection.reports and "operation_retired" not in gap_codes:
        return None
    is_point = is_point_work(source, setup_hours, unit_hours, projection.target_quantity)
    reasons = []
    status = _protected_status(projection, reasons, gap_codes)
    report_segments = _report_segments(projection)
    first_start = _actual_time(projection.first_actual_start)
    confirmed_finish = _actual_time(projection.confirmed_finish)
    intervals = _protected_intervals(status, reasons, report_segments, is_point=is_point)
    machine, operator = _actual_resources(projection, resources, source=source, reasons=reasons,
                                          report_segments=report_segments)
    return {"actual_status": status, "actual_start_time": first_start,
            "actual_end_time": confirmed_finish, "actual_machine_id": machine,
            "actual_operator_id": operator, "ledger_operation_ref": projection.operation_ref,
            "ledger_execution_state": projection.execution_state, "remaining_quantity": projection.remaining_quantity,
            "execution_effective_intervals": intervals, "execution_protection_reasons": tuple(dict.fromkeys(reasons))}


def fact_resource_segments(fact):
    """Return multi-report actual occupancy; the plan row retains the earliest resource pair."""
    if fact.actual_start_time is not None and fact.actual_start_time == fact.actual_end_time:
        return ()
    content = fact.execution_protection_content
    if fact.actual_status == "completed" and content is not None:
        reports = content["projection"]["reports"]
        if len(reports) > 1:
            resources = content["resources"]
            segments = tuple(sorted(
                (start, end,
                 resources[report["actual_machine_ref"]]["business_code"],
                 resources[report["actual_operator_ref"]]["business_code"])
                for report in reports
                for start, end in ((parse_operation_event_time(report["actual_start"]),
                                    parse_operation_event_time(report["actual_end"])),)
                if start < end
            ))
            return segments if len(segments) > 1 else ()
    return ()


def _raise_reconciliation(op_id, state, remaining_quantity, reasons):
    raise AppError(ErrorCode.SCHEDULE_CONFLICT,
                   "工序已有真实报工，但执行资料或剩余安排尚不能安全用于重排。请先补齐或核对报工；本次没有写入排程。",
                   details={"reason": "execution_ledger_requires_reconciliation", "op_id": op_id,
                            "execution_state": state, "data_gaps": list(dict.fromkeys(reasons)),
                            "remaining_quantity": remaining_quantity})


def ensure_ledger_execution_schedulable(facts):
    for op_id, fact in sorted(facts.items()):
        if fact.ledger_operation_ref is None:
            continue
        reasons = list(fact.execution_protection_reasons)
        if fact.ledger_execution_state not in _STATUSES:
            reasons.append("execution_ledger_protection_flags_missing")
        elif fact.actual_status != _STATUSES[fact.ledger_execution_state]:
            reasons.append("execution_ledger_protection_flags_inconsistent")
        if fact.ledger_execution_state in ("started", "partial"):
            reasons.append("execution_ledger_remaining_plan_unavailable")
        if fact.actual_status == "completed":
            intervals = fact.execution_effective_intervals
            if not intervals or fact.actual_start_time is None or fact.actual_end_time is None:
                reasons.append("execution_ledger_actual_interval_missing")
            else:
                span = _occupancy_intervals(intervals)
                if (fact.actual_start_time != span[0][0] or fact.actual_end_time != span[-1][1]
                        or any(start < span[0][0] or end > span[-1][1] for start, end in intervals)):
                    reasons.append("execution_ledger_actual_interval_inconsistent")
        if reasons:
            _raise_reconciliation(op_id, fact.ledger_execution_state, fact.remaining_quantity, reasons)
