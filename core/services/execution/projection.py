"""The only execution aggregation, shared by reads, previews and command guards."""

from dataclasses import replace
from datetime import datetime
from typing import Set

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import closed_write_context, public_ref, reject

from .quality import classify_quality, gap, operation_target
from .totals import quantity_consistency, report_totals


def is_point_work(source, setup_hours, unit_hours, target_quantity):
    values = (setup_hours, unit_hours, target_quantity)
    return (
        source == "internal"
        and type(target_quantity) is int
        and all(
            type(value) in (int, float) and 0 <= value <= 9007199254740991
            for value in values
        )
        and setup_hours == 0
        and (unit_hours == 0 or target_quantity == 0)
    )


def projection_resource_refs(projection: ExecutionProjection) -> Set[str]:
    return {ref for report in projection.reports
            for ref in (report.actual_machine_ref, report.actual_operator_ref) if ref}


def _projection_cache(projection: ExecutionProjection) -> dict:
    return projection.__dict__["_cache"]


def _parsed_times(projection: ExecutionProjection) -> dict:
    cache = _projection_cache(projection)
    by_text = cache.get("parsed_times")
    if by_text is None:
        by_text = {}
        for report in projection.reports:
            for value in (report.actual_start, report.actual_end):
                if value is not None and value not in by_text:
                    by_text[value] = datetime.fromisoformat(value)
        cache["parsed_times"] = by_text
    return by_text


def actual_period(projection: ExecutionProjection):
    cache = _projection_cache(projection)
    cached = cache.get("actual_period")
    if cached is None:
        by_text = cache.get("parsed_times")
        if by_text is not None:
            cached = (
                None if projection.first_actual_start is None else by_text[projection.first_actual_start],
                None if projection.confirmed_finish is None else by_text[projection.confirmed_finish],
            )
        else:
            cached = tuple(
                None if value is None else datetime.fromisoformat(value)
                for value in (projection.first_actual_start, projection.confirmed_finish)
            )
        cache["actual_period"] = cached
    return cached


def report_segments(projection: ExecutionProjection):
    """Each report with its parsed actual start and end, ordered chronologically without merging."""
    cache = _projection_cache(projection)
    cached = cache.get("report_segments")
    if cached is None:
        by_text = _parsed_times(projection)
        cached = tuple(sorted(
            (
                (
                    None if report.actual_start is None else by_text[report.actual_start],
                    None if report.actual_end is None else by_text[report.actual_end],
                    report,
                )
                for report in projection.reports
            ),
            key=lambda segment: (segment[0] or datetime.min, segment[1] or datetime.min),
        ))
        cache["report_segments"] = cached
        if "actual_period" not in cache:
            cache["actual_period"] = (
                None if projection.first_actual_start is None else by_text[projection.first_actual_start],
                None if projection.confirmed_finish is None else by_text[projection.confirmed_finish],
            )
    return cached


def actual_period_basis(projection: ExecutionProjection):
    """Deduplicate and join adjacent periods; keep overlaps and unknowns visible."""
    cache = _projection_cache(projection)
    cached = cache.get("actual_period_basis")
    if cached is not None:
        return cached
    by_text = _parsed_times(projection)
    periods = {
        (
            None if report.actual_start is None else by_text[report.actual_start],
            None if report.actual_end is None else by_text[report.actual_end],
        )
        for report in projection.reports
    }
    unresolved = frozenset((start, end) for start, end in periods if start is None or end is None or end <= start)
    coverage = []
    for start, end in sorted((start, end) for start, end in periods
                             if start is not None and end is not None and end > start):
        if coverage and start == coverage[-1][1]:
            coverage[-1] = (coverage[-1][0], end)
        else:
            coverage.append((start, end))
    cached = (tuple(coverage), unresolved)
    cache["actual_period_basis"] = cached
    if "actual_period" not in cache:
        cache["actual_period"] = (
            None if projection.first_actual_start is None else by_text[projection.first_actual_start],
            None if projection.confirmed_finish is None else by_text[projection.confirmed_finish],
        )
    return cached


def _validate_history_row(sequence, row, previous_ref, *, operation_ref, report_ref):
    try:
        public_ref(row["revision_ref"])
    except WorkbenchCommandRejected:
        reject("报工来源或更正记录损坏，请核对报工数据；仍不行请联系维护人员。", "storage_failure", 500)
    if (row["sequence"] != sequence or row["previous_revision_ref"] != previous_ref
            or row["operation_ref"] != operation_ref or row["report_ref"] != report_ref
            or row["action"] not in (("create",) if sequence == 1 else ("supplement", "correct"))):
        reject("报工来源或更正记录损坏，请核对报工数据；仍不行请联系维护人员。", "storage_failure", 500)
    return row["revision_ref"]


def validate_history_chain(history, *, operation_ref, report_ref):
    previous_ref = None
    for sequence, row in enumerate(history, 1):
        previous_ref = _validate_history_row(sequence, row, previous_ref, operation_ref=operation_ref, report_ref=report_ref)


def validated_correction_history(history):
    corrections = []
    previous = None
    for row in history:
        corrections.append({"revision_ref": row["revision_ref"], "previous_revision_ref": row["previous_revision_ref"],
                            "action": row["action"], "before": previous, "after": row["values"], "reason": row["reason"],
                            "local_operator": row["local_operator"], "declared_operator": row["declared_operator"],
                            "recorded_at": row["revision_at"], "receipt_ref": row["receipt_ref"]})
        previous = row["values"]
    return corrections


def build_correction_history(history, *, operation_ref, report_ref):
    validate_history_chain(history, operation_ref=operation_ref, report_ref=report_ref)
    return validated_correction_history(history)


def _validated_report_dto(history, *, corrections):
    latest = history[-1]
    return ProductionReport(
        **{key: latest[key] for key in ("report_ref", "report_no", "operation_ref", "recorded_against_task_ref",
                                        "recorded_against_plan_ref", "source", "recorded_at",
                                        "revision_ref", "local_operator", "declared_operator")},
        **latest["values"], correction_history=corrections, write_context=closed_write_context())


def report_dto(history, *, operation_ref, report_ref, include_history: bool = True):
    if include_history:
        corrections = build_correction_history(history, operation_ref=operation_ref, report_ref=report_ref)
    else:
        validate_history_chain(history, operation_ref=operation_ref, report_ref=report_ref)
        corrections = []
    return _validated_report_dto(history, corrections=corrections)


def materialize_operation_history(projection: ExecutionProjection, histories, voids) -> ExecutionProjection:
    reports = [
        replace(report, correction_history=validated_correction_history(histories[report.report_ref]))
        for report in projection.reports
    ]
    voided_refs = sorted(
        (report_ref for report_ref in histories if report_ref in voids),
        key=lambda ref: (histories[ref][-1]["recorded_at"], histories[ref][-1]["report_no"]),
    )
    voided = [
        {
            "report": _validated_report_dto(
                histories[report_ref],
                corrections=validated_correction_history(histories[report_ref]),
            ).to_dict(),
            "void_fact": {key: value for key, value in voids[report_ref].items() if key != "request_key"},
        }
        for report_ref in voided_refs
    ]
    return replace(projection, reports=reports, voided_reports=voided)


def _execution_state(reports, totals, complete_reports):
    if complete_reports:
        return "complete"
    if totals.known > 0 or any(report.actual_end for report in reports):
        return "partial"
    return "started" if reports else "unreported"


def _completion(reports, complete_reports):
    if not complete_reports:
        return None, None
    return max(report.actual_end for report in reports), "complete_reports"


def project_execution(operation, reports, *, current_task, comparison_task, plan_identity):
    """No writes, synthesized reports, time-derived hours or scheduler invocations."""
    target, basis, gaps = operation_target(operation)
    totals = report_totals(reports, operation.get("source"))
    gaps.extend(totals.gaps + quantity_consistency(totals, target))
    quantity_complete = target is not None and totals.known == target and totals.unknown == 0
    complete_reports = quantity_complete and totals.records_complete
    state = _execution_state(reports, totals, complete_reports)
    quality = classify_quality(gaps, has_records=bool(reports))
    finish, completion_basis = _completion(reports, complete_reports)
    remaining = None if target is None or totals.unknown or quality == "invalid" else target - totals.known
    if state not in ("complete", "unreported"):
        gaps.append(gap("remaining_plan_unavailable", "这道工序还没做完的部分暂无确认的安排，系统没有按剩余数量推算时长。"))
    return ExecutionProjection(
        operation_ref=operation["operation_ref"], current_task_ref=current_task["task_ref"] if current_task else None,
        comparison_task_ref=comparison_task["task_ref"] if comparison_task else None, plan_identity=plan_identity,
        target_quantity=target, target_basis=basis, known_completed_quantity=totals.known, quantity_complete=quantity_complete,
        unknown_record_count=totals.unknown, records_complete=totals.records_complete,
        first_actual_start=min(totals.starts) if totals.starts else None,
        confirmed_finish=finish, execution_state=state, completion_basis=completion_basis,
        data_quality=quality, reports=reports,
        remaining_quantity=remaining, remaining_plan=None, data_gaps=gaps, write_context=closed_write_context())
