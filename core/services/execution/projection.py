"""The only execution aggregation, shared by reads, previews and command guards."""

from core.models.operation_execution_event import parse_operation_event_time
from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import closed_write_context

from .legacy import legacy_evidence
from .quality import classify_quality, gap, operation_target
from .totals import merge_legacy_totals, quantity_consistency, report_totals


def report_dto(history):
    latest = history[-1]
    corrections = []
    previous = None
    for row in history:
        corrections.append({"revision_ref": row["revision_ref"], "previous_revision_ref": row["previous_revision_ref"],
                            "action": row["action"], "before": previous, "after": row["values"], "reason": row["reason"],
                            "local_operator": row["local_operator"], "declared_operator": row["declared_operator"],
                            "recorded_at": row["revision_at"], "receipt_ref": row.get("receipt_ref")})
        previous = row["values"]
    return ProductionReport(
        **{key: latest[key] for key in ("report_ref", "report_no", "operation_ref", "recorded_against_task_ref",
                                        "recorded_against_plan_ref", "source", "legacy_fact_ref", "recorded_at",
                                        "revision_ref", "local_operator", "declared_operator")},
        **latest["values"], correction_history=corrections, write_context=closed_write_context())


def _execution_state(reports, totals, evidence, complete_reports):
    if evidence.finishes or complete_reports:
        return "complete"
    if evidence.state in ("pause", "exception"):
        return "paused" if evidence.state == "pause" else "exception"
    if totals.known > 0 or any(report.actual_end for report in reports):
        return "partial"
    return "started" if reports or totals.starts else "unreported"


def _completion(reports, evidence, complete_reports):
    times = [parse_operation_event_time(row["event_time"]).isoformat(timespec="seconds") for row in evidence.finishes]
    if complete_reports:
        times.extend(report.actual_end for report in reports if report.actual_end)
    basis = "legacy_finish_event" if evidence.finishes else "complete_reports" if complete_reports else None
    return max(times) if times else None, basis


def project_execution(operation, reports, legacy, *, current_task, comparison_task, plan_identity, now, unresolved=False):
    """No writes, synthesized reports, time-derived hours or scheduler invocations."""
    target, basis, gaps = operation_target(operation, unresolved)
    evidence = legacy_evidence(legacy, now)
    totals = report_totals(reports, operation.get("source"))
    merge_legacy_totals(totals, evidence)
    gaps.extend(evidence.gaps + totals.gaps + quantity_consistency(totals, target, evidence.finishes))
    quantity_complete = target is not None and totals.known == target and totals.unknown == 0
    complete_reports = quantity_complete and totals.records_complete
    state = _execution_state(reports, totals, evidence, complete_reports)
    quality = classify_quality(gaps, legacy_uncovered=totals.legacy_uncovered, has_records=bool(reports or legacy))
    finish, completion_basis = _completion(reports, evidence, complete_reports)
    remaining = None if target is None or totals.unknown or quality == "invalid" else target - totals.known
    if state not in ("complete", "unreported"):
        gaps.append(gap("remaining_plan_unavailable", "尚无已核实的剩余安排；没有按剩余数量推算时长。"))
    return ExecutionProjection(
        operation_ref=operation["operation_ref"], current_task_ref=current_task["task_ref"] if current_task else None,
        comparison_task_ref=comparison_task["task_ref"] if comparison_task else None, plan_identity=plan_identity,
        target_quantity=target, target_basis=basis, known_completed_quantity=totals.known, quantity_complete=quantity_complete,
        unknown_record_count=totals.unknown, records_complete=totals.records_complete,
        first_actual_start=min(totals.starts) if totals.starts else None,
        confirmed_finish=finish, execution_state=state, completion_basis=completion_basis,
        data_quality=quality, reports=reports, legacy_facts=evidence.records,
        remaining_quantity=remaining, remaining_plan=None, data_gaps=gaps, write_context=closed_write_context())
