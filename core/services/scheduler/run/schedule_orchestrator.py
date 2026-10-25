from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext

from .schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from .schedule_candidate_runner import run_candidate_comparison
from .schedule_candidate_summary import candidate_comparison_public_summary
from .schedule_input_contracts import ScheduleRunInput
from .schedule_payload_contract import ValidatedSchedulePayload, build_validated_schedule_payload


@dataclass
class ScheduleOrchestrationOutcome:
    validated_schedule_payload: ValidatedSchedulePayload
    result_summary_obj: Dict[str, Any]
    candidate_comparison: CandidateComparisonOutcome


def _run_plan_selection(
    *,
    schedule_input: ScheduleRunInput,
    strict_mode: bool,
    candidate_comparison_fn: Any = None,
) -> Tuple[CandidatePlan, Optional[Dict[str, Any]], Optional[Dict[str, Any]], CandidateComparisonOutcome]:
    candidate_comparison = (candidate_comparison_fn or run_candidate_comparison)(
        schedule_input=schedule_input,
        run_time_budget_seconds=schedule_input.run_time_budget_seconds,
        strict_mode=strict_mode,
    )
    adopted_plan: CandidatePlan = candidate_comparison.selection.selected_plan
    return adopted_plan, adopted_plan.graph_analysis_public, adopted_plan.graph_analysis_diagnostics, candidate_comparison


def orchestrate_schedule_run(
    *,
    schedule_input: ScheduleRunInput,
    version: int,
    strict_mode: bool,
    build_result_summary_fn: Any,
    point_validator: Any = None,
    candidate_comparison_fn: Any = None,
) -> ScheduleOrchestrationOutcome:
    """Compute candidates and their summary using an already prepared run input."""
    adopted_plan, graph_analysis_public, graph_analysis_diagnostics, candidate_comparison = _run_plan_selection(
        schedule_input=schedule_input,
        strict_mode=strict_mode,
        candidate_comparison_fn=candidate_comparison_fn,
    )
    validated_schedule_payload = build_validated_schedule_payload(
        adopted_plan.results,
        allowed_op_ids=schedule_input.schedule_output_allowed_op_ids,
        operations=schedule_input.payload_validation_operations,
        operation_sources=schedule_input.operation_sources,
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        schedule_errors=adopted_plan.summary.errors if adopted_plan.summary is not None else [],
        point_validator=point_validator,
    )

    time_budget_seconds = int(adopted_plan.time_budget_seconds)
    summary_ctx = SummaryBuildContext(
        cfg=schedule_input.cfg,
        version=version,
        normalized_batch_ids=schedule_input.normalized_batch_ids,
        start_dt=schedule_input.start_dt_norm,
        end_date=schedule_input.end_date_norm,
        batches=schedule_input.batches,
        operations=schedule_input.operations,
        results=adopted_plan.results,
        summary=adopted_plan.summary,
        used_strategy=adopted_plan.used_strategy,
        used_params=adopted_plan.used_params,
        algo_mode=adopted_plan.algo_mode,
        objective_name=adopted_plan.objective_name,
        time_budget_seconds=time_budget_seconds,
        best_score=adopted_plan.score,
        best_metrics=adopted_plan.metrics,
        attempts=adopted_plan.attempts,
        improvement_trace=adopted_plan.improvement_trace,
        frozen_op_ids=schedule_input.frozen_op_ids,
        search_report=adopted_plan.search_report,
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        scheduled_op_ids=validated_schedule_payload.scheduled_op_ids,
        freeze_meta=schedule_input.freeze_meta,
        downtime_meta=schedule_input.downtime_meta,
        resource_pool_meta=schedule_input.resource_pool_meta,
        readiness_gate_enabled=schedule_input.readiness_gate_enabled,
        algo_stats=adopted_plan.algo_stats,
        graph_analysis_public=graph_analysis_public,
        graph_analysis_diagnostics=graph_analysis_diagnostics,
        candidate_comparison_public=candidate_comparison_public_summary(candidate_comparison),
        execution_snapshot_revision=schedule_input.execution_snapshot_revision,
        execution_snapshot_op_ids=schedule_input.execution_snapshot_op_ids,
        execution_snapshot_op_count=schedule_input.execution_snapshot_op_count,
        simulate=True,
        t0=schedule_input.t0,
    )

    result_summary_obj = build_result_summary_fn(ctx=summary_ctx)

    return ScheduleOrchestrationOutcome(
        validated_schedule_payload=validated_schedule_payload,
        result_summary_obj=result_summary_obj,
        candidate_comparison=candidate_comparison,
    )
