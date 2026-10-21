from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext

from .schedule_candidate_plan import CandidatePlan
from .schedule_candidate_runner import run_candidate_comparison
from .schedule_candidate_summary import candidate_comparison_public_summary
from .schedule_input_contracts import ScheduleRunInput
from .schedule_payload_contract import ValidatedSchedulePayload, build_validated_schedule_payload

_LOGGER = logging.getLogger(__name__)


@dataclass
class ScheduleOrchestrationOutcome:
    version: int
    results: List[Any]
    summary: Any
    validated_schedule_payload: ValidatedSchedulePayload
    used_strategy: Any
    used_params: Dict[str, Any]
    best_metrics: Any
    best_score: Optional[Tuple[float, ...]]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    algo_stats: Dict[str, Any]
    time_budget_seconds: int
    search_report: Dict[str, Any]
    warning_merge_status: Dict[str, Any]
    algo_warnings: List[str]
    overdue_items: List[Any]
    result_status: str
    result_summary_obj: Dict[str, Any]
    time_cost_ms: int
    candidate_comparison: Any


def _graph_analysis_for_summary(candidate_comparison: Any, adopted_plan: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    public = getattr(adopted_plan, "graph_analysis_public", None)
    diagnostics = getattr(adopted_plan, "graph_analysis_diagnostics", None)
    if public is not None or diagnostics is not None:
        return public, diagnostics

    for candidate in list(getattr(candidate_comparison, "candidates", None) or []):
        if str(getattr(candidate, "kind", "") or "") != "critical_chain":
            continue
        public = getattr(candidate, "graph_analysis_public", None)
        diagnostics = getattr(candidate, "graph_analysis_diagnostics", None)
        if public is not None or diagnostics is not None:
            return public, diagnostics
    return None, None


def _merge_summary_warnings(summary: Any, algo_warnings: List[str]) -> Dict[str, Any]:
    warning_merge_status: Dict[str, Any] = {
        "summary_merge_attempted": bool(algo_warnings),
        "summary_merge_failed": False,
        "summary_merge_error": None,
    }

    summary_warnings = getattr(summary, "warnings", None)
    if summary_warnings is None:
        summary_warnings = []
        if summary is None:
            warning_merge_status["summary_merge_failed"] = bool(algo_warnings)
            warning_merge_status["summary_merge_error"] = "summary_missing"
        else:
            try:
                summary.warnings = summary_warnings
            except (AttributeError, TypeError) as exc:
                warning_merge_status["summary_merge_failed"] = True
                warning_merge_status["summary_merge_error"] = "summary_warnings_assignment_failed"
                _LOGGER.warning("summary warnings assignment failed: %s", exc)

    if algo_warnings:
        if hasattr(summary_warnings, "extend"):
            summary_warnings.extend(algo_warnings)
        else:
            warning_merge_status["summary_merge_failed"] = True
            warning_merge_status["summary_merge_error"] = (
                warning_merge_status["summary_merge_error"] or "summary_warnings_unavailable"
            )

    return warning_merge_status


def _run_plan_selection(
    *,
    schedule_input: ScheduleRunInput,
    strict_mode: bool,
    logger: Any = None,
    candidate_comparison_fn: Any = None,
) -> Tuple[CandidatePlan, Optional[Dict[str, Any]], Optional[Dict[str, Any]], Any]:
    candidate_comparison = (candidate_comparison_fn or run_candidate_comparison)(
        schedule_input=schedule_input,
        run_time_budget_seconds=schedule_input.run_time_budget_seconds,
        strict_mode=bool(strict_mode), logger=logger,
    )
    adopted_plan: CandidatePlan = candidate_comparison.selection.selected_plan
    graph_public, graph_diagnostics = _graph_analysis_for_summary(candidate_comparison, adopted_plan)
    return adopted_plan, graph_public, graph_diagnostics, candidate_comparison


def orchestrate_schedule_run(
    *,
    schedule_input: ScheduleRunInput,
    version: int,
    strict_mode: bool,
    build_result_summary_fn: Any,
    logger: Any = None,
    point_validator: Any = None,
    candidate_comparison_fn: Any = None,
) -> ScheduleOrchestrationOutcome:
    """Compute candidates and their summary using an already prepared run input."""
    adopted_plan, graph_analysis_public, graph_analysis_diagnostics, candidate_comparison = _run_plan_selection(
        schedule_input=schedule_input,
        logger=logger,
        strict_mode=bool(strict_mode),
        candidate_comparison_fn=candidate_comparison_fn,
    )
    validated_schedule_payload = build_validated_schedule_payload(
        adopted_plan.results,
        allowed_op_ids=schedule_input.schedule_output_allowed_op_ids,
        operations=schedule_input.payload_validation_operations,
        operation_sources=getattr(schedule_input, "operation_sources", None),
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        schedule_errors=list(getattr(adopted_plan.summary, "errors", None) or []),
        point_validator=point_validator,
    )

    algo_warnings = list(schedule_input.algo_warnings or [])
    warning_merge_status = _merge_summary_warnings(
        adopted_plan.summary,
        algo_warnings,
    )

    summary_ctx = SummaryBuildContext(
        cfg=schedule_input.cfg,
        version=int(version),
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
        time_budget_seconds=int(adopted_plan.time_budget_seconds or 0),
        best_score=adopted_plan.score,
        best_metrics=adopted_plan.metrics,
        best_order=adopted_plan.best_order,
        attempts=adopted_plan.attempts,
        improvement_trace=adopted_plan.improvement_trace,
        frozen_op_ids=set(schedule_input.frozen_op_ids),
        search_report=adopted_plan.search_report,
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        scheduled_op_ids=set(validated_schedule_payload.scheduled_op_ids),
        freeze_meta=schedule_input.freeze_meta,
        input_build_outcome=schedule_input.algo_input_outcome,
        downtime_meta=schedule_input.downtime_meta,
        resource_pool_meta=schedule_input.resource_pool_meta,
        readiness_gate_enabled=bool(schedule_input.readiness_gate_enabled),
        algo_stats=adopted_plan.algo_stats,
        algo_warnings=algo_warnings,
        warning_merge_status=warning_merge_status,
        graph_analysis_public=graph_analysis_public,
        graph_analysis_diagnostics=graph_analysis_diagnostics,
        candidate_comparison_public=(
            candidate_comparison_public_summary(candidate_comparison)
            if candidate_comparison is not None
            else None
        ),
        execution_snapshot_revision=schedule_input.execution_snapshot_revision,
        execution_snapshot_op_ids=schedule_input.execution_snapshot_op_ids,
        execution_snapshot_op_count=schedule_input.execution_snapshot_op_count,
        simulate=True,
        t0=schedule_input.t0,
    )

    overdue_items, result_status, result_summary_obj, time_cost_ms = build_result_summary_fn(
        ctx=summary_ctx,
        logger=logger,
    )

    return ScheduleOrchestrationOutcome(
        version=int(version),
        results=adopted_plan.results,
        summary=adopted_plan.summary,
        validated_schedule_payload=validated_schedule_payload,
        used_strategy=adopted_plan.used_strategy,
        used_params=adopted_plan.used_params,
        best_metrics=adopted_plan.metrics,
        best_score=adopted_plan.score,
        best_order=adopted_plan.best_order,
        attempts=adopted_plan.attempts,
        improvement_trace=adopted_plan.improvement_trace,
        algo_mode=adopted_plan.algo_mode,
        objective_name=adopted_plan.objective_name,
        algo_stats=adopted_plan.algo_stats,
        time_budget_seconds=int(adopted_plan.time_budget_seconds or 0),
        search_report=adopted_plan.search_report,
        warning_merge_status=warning_merge_status,
        algo_warnings=algo_warnings,
        overdue_items=overdue_items,
        result_status=result_status,
        result_summary_obj=result_summary_obj,
        time_cost_ms=int(time_cost_ms),
        candidate_comparison=candidate_comparison,
    )
