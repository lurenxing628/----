"""The only execution aggregation, shared by reads, previews and command guards."""

from typing import Set

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import closed_write_context, public_ref, reject

from .quality import classify_quality, gap, operation_target
from .totals import quantity_consistency, report_totals


def projection_resource_refs(projection: ExecutionProjection) -> Set[str]:
    return {ref for report in projection.reports
            for ref in (report.actual_machine_ref, report.actual_operator_ref) if ref}


def report_dto(history, *, operation_ref, report_ref):
    latest = history[-1]
    corrections = []
    previous = None
    previous_ref = None
    for sequence, row in enumerate(history, 1):
        try:
            public_ref(row["revision_ref"])
        except WorkbenchCommandRejected:
            reject("报工来源或更正记录损坏，请核对报工数据；仍不行请联系维护人员。", "storage_failure", 500)
        if (row["sequence"] != sequence or row["previous_revision_ref"] != previous_ref
                or row["operation_ref"] != operation_ref or row["report_ref"] != report_ref
                or row["action"] not in (("create",) if sequence == 1 else ("supplement", "correct"))):
            reject("报工来源或更正记录损坏，请核对报工数据；仍不行请联系维护人员。", "storage_failure", 500)
        previous_ref = row["revision_ref"]
        corrections.append({"revision_ref": row["revision_ref"], "previous_revision_ref": row["previous_revision_ref"],
                            "action": row["action"], "before": previous, "after": row["values"], "reason": row["reason"],
                            "local_operator": row["local_operator"], "declared_operator": row["declared_operator"],
                            "recorded_at": row["revision_at"], "receipt_ref": row.get("receipt_ref")})
        previous = row["values"]
    return ProductionReport(
        **{key: latest[key] for key in ("report_ref", "report_no", "operation_ref", "recorded_against_task_ref",
                                        "recorded_against_plan_ref", "source", "recorded_at",
                                        "revision_ref", "local_operator", "declared_operator")},
        **latest["values"], correction_history=corrections, write_context=closed_write_context())


def _execution_state(reports, totals, complete_reports):
    if complete_reports:
        return "complete"
    if totals.known > 0 or any(report.actual_end for report in reports):
        return "partial"
    return "started" if reports or totals.starts else "unreported"


def _completion(reports, complete_reports):
    if not complete_reports:
        return None, None
    times = [report.actual_end for report in reports if report.actual_end]
    return max(times) if times else None, "complete_reports"


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
