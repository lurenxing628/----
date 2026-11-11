"""In-memory candidate computation. No worker admission, version allocation or publish."""

from core.infrastructure.connection_guards import is_query_only
from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_compute import CandidateRunComputation
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_public_summary
from core.services.scheduler.summary.schedule_summary import build_result_summary
from core.services.workbench.facts.run_input_rows import fail

from .candidate_adoption_constraints import (
    evaluate_schedule_constraints,
    prepare_schedule_validation_context,
)
from .compute_validation import prepare_candidate_validation_context
from .input import prepare_business_input, prepare_solver_input
from .input_runtime import prepare_solver_resources
from .piece_adoption import prepare_piece_validation_context, validate_piece_candidate
from .preflight_facts import PreflightFacts


def compute_candidate_run(conn, normalized_input, execution_projections, *, capture, dispositions) -> CandidateRunComputation:
    """Compute actual candidate rows under one read snapshot; worker owns run lock.

    capture is the worker's production facts capture; execution_projections and
    dispositions are the already validated projections and the classification
    archived by that run's admission.
    """
    with PreflightFacts.open(conn, capture=capture) as facts:
        # The private continuation consumes this preparation in the same read snapshot.
        business = prepare_business_input(conn, normalized_input, execution_projections, facts=facts,
                                          admitted_dispositions=dispositions)
        return _compute_in_read_snapshot(conn, business, _prepared_version(business))


def _prepared_version(business):
    # baseline_version is read straight from the captured ScheduleHistory rows; this is its only check.
    version = business.baseline_version
    if type(version) is not int or version < 0:
        fail("invalid_version_context", "Version context must be an explicit non-negative integer.")
    return version


def _candidate_outcomes(conn, business, comparison, *, calendar, validation_context):
    outcomes = {}
    selected_key = comparison.selection.selected_candidate_key
    with read_evidence_scope(conn):
        if business.piece_scope is not None:
            piece_context = {
                **prepare_piece_validation_context(conn, business),
                "validation_context": validation_context,
            }
            for candidate in comparison.candidates:
                failure_details = (
                    candidate.summary.failure_details
                    if candidate.candidate_key == selected_key
                    else ()
                )
                outcomes[candidate.candidate_key] = validate_piece_candidate(
                    conn,
                    prepared=business,
                    calendar=calendar,
                    payload=candidate.results,
                    context=piece_context,
                    failure_details=failure_details,
                )
        else:
            shared_context = prepare_schedule_validation_context(
                business,
                validation_context=validation_context,
            )
            for candidate in comparison.candidates:
                failure_details = (
                    candidate.summary.failure_details
                    if candidate.candidate_key == selected_key
                    else ()
                )
                outcome = evaluate_schedule_constraints(
                    business,
                    calendar,
                    candidate.results,
                    purpose="publication",
                    context=shared_context,
                    failure_details=failure_details,
                )
                if outcome.issues:
                    first = outcome.issues[0]
                    fail(first["code"], first["message"])
                outcomes[candidate.candidate_key] = outcome
    return outcomes


def _computation_state(business, comparison, outcomes):
    selected = comparison.selection.selected_plan
    selected_ids = outcomes[selected.candidate_key].validated_payload.scheduled_op_ids
    # The unified search returns only completed candidates; partial means the selected plan's scope.
    is_partial = (selected_ids != business.allowed_op_ids
                  or any(row["status"] == "skipped" for row in business.dispositions))
    return "partial" if is_partial else "complete"


def _build_result_summary(
    business,
    resources,
    comparison,
    *,
    version: int,
    selected_payload,
):
    adopted_plan = comparison.selection.selected_plan
    summary_ctx = SummaryBuildContext(
        cfg=business.config,
        version=version,
        normalized_batch_ids=business.normalized_batch_ids,
        start_dt=business.start,
        end_date=business.end_date,
        batches=business.batches,
        operations=business.operations,
        results=adopted_plan.results,
        summary=adopted_plan.summary,
        used_strategy=adopted_plan.used_strategy,
        used_params=adopted_plan.used_params,
        algo_mode=adopted_plan.algo_mode,
        objective_name=adopted_plan.objective_name,
        time_budget_seconds=int(adopted_plan.time_budget_seconds),
        best_score=adopted_plan.score,
        best_metrics=adopted_plan.metrics,
        frozen_op_ids=business.seeds.frozen_op_ids,
        missing_internal_resource_op_ids=business.missing_internal_resource_op_ids,
        scheduled_op_ids=selected_payload.scheduled_op_ids,
        freeze_meta=business.seeds.freeze_meta,
        downtime_meta=resources.downtime_meta,
        resource_pool_meta=resources.resource_pool_meta,
        readiness_gate_enabled=business.readiness_gate_enabled,
        algo_stats=adopted_plan.algo_stats,
        graph_analysis_public=adopted_plan.graph_analysis_public,
        graph_analysis_diagnostics=adopted_plan.graph_analysis_diagnostics,
        candidate_comparison_public=candidate_comparison_public_summary(comparison),
        execution_snapshot_revision=business.execution_guard.execution_snapshot_revision,
        execution_snapshot_op_ids=list(business.execution_guard.execution_snapshot_op_ids),
        execution_snapshot_op_count=business.execution_guard.execution_snapshot_op_count,
        simulate=True,
        t0=business.t0,
    )
    return build_result_summary(ctx=summary_ctx)


def _compute_in_read_snapshot(conn, business, version):
    """Private continuation after preparation in the current snapshot."""
    if not conn.in_transaction or not is_query_only(conn):
        fail("candidate_read_snapshot_lost", "Candidate computation requires its active read-only snapshot.")
    solver_input = prepare_solver_input(business)
    resources = prepare_solver_resources(business, solver_input)
    validation_context = prepare_candidate_validation_context(business)
    comparison = run_candidate_comparison(solver_input=solver_input, resources=resources)
    outcomes = _candidate_outcomes(
        conn,
        business,
        comparison,
        calendar=resources.calendar_engine,
        validation_context=validation_context,
    )
    selected_payload = outcomes[comparison.selection.selected_candidate_key].validated_payload
    result_summary_obj = _build_result_summary(
        business,
        resources,
        comparison,
        version=version,
        selected_payload=selected_payload,
    )
    state = _computation_state(business, comparison, outcomes)
    return CandidateRunComputation(
        schedule_input=business,
        candidate_comparison=comparison,
        result_summary_obj=result_summary_obj,
        candidate_outcomes=outcomes,
        dispositions=business.dispositions,
        state=state,
    )
