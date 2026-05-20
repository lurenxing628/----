from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..summary.schedule_summary_types import SummaryBuildContext
from .schedule_candidate_runner import run_candidate_comparison
from .schedule_candidate_summary import candidate_comparison_public_summary
from .schedule_graph_report import prepare_schedule_graph_for_dispatch
from .schedule_input_collector import ScheduleRunInput
from .schedule_persistence import ValidatedSchedulePayload, build_validated_schedule_payload

_LOGGER = logging.getLogger(__name__)
_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}


def _normalize_summary_merge_error(reason: Any) -> Optional[str]:
    text = str(reason or "").strip()
    if not text:
        return None
    if text in _SUMMARY_MERGE_ERROR_CODES:
        return text
    return "summary_warnings_assignment_failed"


@dataclass(frozen=True)
class ScheduleSummaryContract:
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.payload)


@dataclass
class ScheduleOrchestrationOutcome:
    version: int
    results: List[Any]
    summary: Any
    summary_contract: ScheduleSummaryContract
    validated_schedule_payload: ValidatedSchedulePayload
    used_strategy: Any
    used_params: Dict[str, Any]
    best_metrics: Any
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    algo_stats: Dict[str, Any]
    time_budget_seconds: int
    warning_merge_status: Dict[str, Any]
    algo_warnings: List[str]
    overdue_items: List[Any]
    result_status: str
    result_summary_obj: Dict[str, Any]
    result_summary_json: str
    time_cost_ms: int
    candidate_comparison: Any


@dataclass
class _NormalizedOptimizerOutcome:
    results: List[Any]
    summary: Any
    used_strategy: Any
    used_params: Dict[str, Any]
    best_metrics: Any
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    algo_stats: Dict[str, Any]
    time_budget_seconds: int


def _summary_field(summary: Any, field: str, default: Any) -> Any:
    if isinstance(summary, dict):
        return summary.get(field, default)
    return getattr(summary, field, default)


def _summary_warnings(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    if isinstance(result_summary_obj, dict) and "warnings" in result_summary_obj:
        raw_warnings = result_summary_obj.get("warnings")
        if raw_warnings is None:
            return []
        if isinstance(raw_warnings, str):
            return [raw_warnings] if raw_warnings else []
        try:
            return [str(item) for item in list(raw_warnings or []) if str(item)]
        except Exception:
            text = str(raw_warnings).strip()
            return [text] if text else []
    return list(_summary_field(summary, "warnings", []) or [])


def _summary_errors(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    if isinstance(result_summary_obj, dict) and "errors" in result_summary_obj:
        raw_errors = result_summary_obj.get("errors")
    else:
        raw_errors = _summary_field(summary, "errors", [])
    if raw_errors is None:
        return []
    if isinstance(raw_errors, str):
        return [raw_errors] if raw_errors else []
    try:
        return [str(item) for item in list(raw_errors or []) if str(item)]
    except Exception:
        text = str(raw_errors).strip()
        return [text] if text else []


def _summary_counts(result_summary_obj: Dict[str, Any], summary: Any) -> Dict[str, int]:
    raw_counts = result_summary_obj.get("counts") if isinstance(result_summary_obj, dict) else {}
    counts = dict(raw_counts or {}) if isinstance(raw_counts, dict) else {}

    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    total_ops = _to_int(counts.get("op_count", counts.get("total_ops", _summary_field(summary, "total_ops", 0))))
    scheduled_ops = _to_int(counts.get("scheduled_ops", _summary_field(summary, "scheduled_ops", 0)))
    failed_ops = _to_int(counts.get("failed_ops", _summary_field(summary, "failed_ops", 0)))
    counts["op_count"] = total_ops
    counts["total_ops"] = total_ops
    counts["scheduled_ops"] = scheduled_ops
    counts["failed_ops"] = failed_ops
    return counts


def _build_summary_contract(summary: Any, *, result_summary_obj: Dict[str, Any]) -> ScheduleSummaryContract:
    payload = dict(result_summary_obj or {})
    warnings = _summary_warnings(result_summary_obj, summary)
    errors = _summary_errors(result_summary_obj, summary)
    counts = _summary_counts(result_summary_obj, summary)
    payload.update(
        {
            "success": bool(_summary_field(summary, "success", False)),
            "total_ops": int(counts.get("total_ops") or 0),
            "scheduled_ops": int(counts.get("scheduled_ops") or 0),
            "failed_ops": int(counts.get("failed_ops") or 0),
            "warnings": list(warnings),
            "errors": list(errors),
            "duration_seconds": float(_summary_field(summary, "duration_seconds", 0.0) or 0.0),
            "degradation_events": list(payload.get("degradation_events") or []),
            "degradation_counters": dict(payload.get("degradation_counters") or {}),
            "degraded_success": bool(payload.get("degraded_success") or False),
            "degraded_causes": list(payload.get("degraded_causes") or []),
            "error_count": int(payload.get("error_count") or len(errors)),
            "errors_sample": list(payload.get("errors_sample") or errors[:10]),
            "counts": counts,
        }
    )
    payload["error_count"] = max(int(payload.get("error_count") or 0), len(payload["errors_sample"]), len(errors))
    return ScheduleSummaryContract(payload=payload)


def _normalize_optimizer_outcome(optimizer_outcome: Any) -> _NormalizedOptimizerOutcome:
    from .schedule_optimizer import OptimizationOutcome

    if not isinstance(optimizer_outcome, OptimizationOutcome):
        raise TypeError("optimize_schedule_fn must return OptimizationOutcome")
    return _NormalizedOptimizerOutcome(
        results=list(optimizer_outcome.results or []),
        summary=optimizer_outcome.summary,
        used_strategy=optimizer_outcome.used_strategy,
        used_params=dict(optimizer_outcome.used_params or {}),
        best_metrics=optimizer_outcome.metrics,
        best_score=tuple(optimizer_outcome.best_score or ()),
        best_order=list(optimizer_outcome.best_order or []),
        attempts=list(optimizer_outcome.attempts or []),
        improvement_trace=list(optimizer_outcome.improvement_trace or []),
        algo_mode=str(optimizer_outcome.algo_mode or ""),
        objective_name=str(optimizer_outcome.objective_name or ""),
        algo_stats=dict(optimizer_outcome.algo_stats or {}),
        time_budget_seconds=int(optimizer_outcome.time_budget_seconds or 0),
    )


def _normalize_candidate_plan(candidate_plan: Any) -> _NormalizedOptimizerOutcome:
    return _NormalizedOptimizerOutcome(
        results=list(getattr(candidate_plan, "results", None) or []),
        summary=getattr(candidate_plan, "summary", None),
        used_strategy=getattr(candidate_plan, "used_strategy", None),
        used_params=dict(getattr(candidate_plan, "used_params", None) or {}),
        best_metrics=getattr(candidate_plan, "metrics", None),
        best_score=tuple(getattr(candidate_plan, "score", None) or ()),
        best_order=list(getattr(candidate_plan, "best_order", None) or []),
        attempts=list(getattr(candidate_plan, "attempts", None) or []),
        improvement_trace=list(getattr(candidate_plan, "improvement_trace", None) or []),
        algo_mode=str(getattr(candidate_plan, "algo_mode", "") or ""),
        objective_name=str(getattr(candidate_plan, "objective_name", "") or ""),
        algo_stats=dict(getattr(candidate_plan, "algo_stats", None) or {}),
        time_budget_seconds=int(getattr(candidate_plan, "time_budget_seconds", 0) or 0),
    )


def _candidate_comparison_enabled(cfg: Any) -> bool:
    return str(getattr(cfg, "graph_analysis_mode", "off") or "off").strip().lower() == "on"


def _candidate_weight_count(cfg: Any) -> int:
    value = getattr(cfg, "graph_candidate_weight_count", 5)
    return 5 if value is None or str(value).strip() == "" else int(value)


def _candidate_selection_policy(cfg: Any) -> str:
    return str(getattr(cfg, "graph_selection_policy", "balanced") or "balanced").strip().lower()


def _candidate_overdue_tolerance_count(cfg: Any) -> int:
    value = getattr(cfg, "graph_overdue_tolerance_count", 1)
    return 1 if value is None or str(value).strip() == "" else int(value)


def _candidate_tardiness_tolerance_ratio(cfg: Any) -> float:
    value = getattr(cfg, "graph_tardiness_tolerance_ratio", 0.10)
    return 0.10 if value is None or str(value).strip() == "" else float(value)


def _run_optimizer_once(
    *,
    schedule_input: ScheduleRunInput,
    optimize_schedule_fn: Any,
    strict_mode: bool,
    logger: Any,
    graph_preparation: Optional[Any] = None,
) -> Tuple[_NormalizedOptimizerOutcome, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if graph_preparation is None:
        graph_preparation = prepare_schedule_graph_for_dispatch(schedule_input)
    optimizer_outcome = _normalize_optimizer_outcome(
        optimize_schedule_fn(
            calendar_service=schedule_input.cal_svc,
            cfg_svc=schedule_input.cfg_svc,
            cfg=schedule_input.cfg,
            algo_ops_to_schedule=schedule_input.algo_ops_to_schedule,
            batches=schedule_input.batches,
            start_dt=schedule_input.start_dt_norm,
            end_date=schedule_input.end_date_norm,
            downtime_map=schedule_input.downtime_map,
            seed_results=schedule_input.seed_results,
            resource_pool=schedule_input.resource_pool,
            version=schedule_input.optimizer_seed_version,
            logger=logger,
            readiness_gate_enabled=bool(schedule_input.readiness_gate_enabled),
            strict_mode=bool(strict_mode),
            graph_ready_context=graph_preparation.graph_ready_context,
            graph_dispatch_mode_override=graph_preparation.graph_dispatch_mode_override,
        )
    )
    return (
        optimizer_outcome,
        graph_preparation.graph_analysis_public,
        graph_preparation.graph_analysis_diagnostics,
    )


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
                _normalize_summary_merge_error(warning_merge_status.get("summary_merge_error")) or "summary_warnings_unavailable"
            )

    warning_merge_status["summary_merge_error"] = _normalize_summary_merge_error(warning_merge_status.get("summary_merge_error"))
    return warning_merge_status


def orchestrate_schedule_run(
    svc: Any,
    *,
    schedule_input: ScheduleRunInput,
    simulate: bool,
    strict_mode: bool,
    optimize_schedule_fn: Any,
    build_result_summary_fn: Any,
) -> ScheduleOrchestrationOutcome:
    candidate_comparison = None
    if _candidate_comparison_enabled(schedule_input.cfg):
        candidate_comparison = run_candidate_comparison(
            schedule_input=schedule_input,
            optimize_schedule_fn=optimize_schedule_fn,
            run_time_budget_seconds=getattr(schedule_input, "run_time_budget_seconds", None),
            weight_count=_candidate_weight_count(schedule_input.cfg),
            selection_policy=_candidate_selection_policy(schedule_input.cfg),
            graph_overdue_tolerance_count=_candidate_overdue_tolerance_count(schedule_input.cfg),
            graph_tardiness_tolerance_ratio=_candidate_tardiness_tolerance_ratio(schedule_input.cfg),
            strict_mode=bool(strict_mode),
            logger=svc.logger,
        )
        adopted_plan = candidate_comparison.selection.selected_plan
        optimizer_outcome = _normalize_candidate_plan(adopted_plan)
        graph_analysis_public, graph_analysis_diagnostics = _graph_analysis_for_summary(candidate_comparison, adopted_plan)
    else:
        optimizer_outcome, graph_analysis_public, graph_analysis_diagnostics = _run_optimizer_once(
            schedule_input=schedule_input,
            optimize_schedule_fn=optimize_schedule_fn,
            strict_mode=bool(strict_mode),
            logger=svc.logger,
        )

    validated_schedule_payload = build_validated_schedule_payload(
        optimizer_outcome.results,
        allowed_op_ids=set(schedule_input.reschedulable_op_ids),
        operations=list(schedule_input.reschedulable_operations or []),
        missing_internal_resource_op_ids=set(schedule_input.missing_internal_resource_op_ids or set()),
    )

    warning_merge_status = _merge_summary_warnings(
        optimizer_outcome.summary,
        list(schedule_input.algo_warnings or []),
    )

    with svc.tx_manager.transaction():
        version = int(svc.history_repo.allocate_next_version())

    summary_ctx = SummaryBuildContext(
        cfg=schedule_input.cfg,
        version=version,
        normalized_batch_ids=schedule_input.normalized_batch_ids,
        start_dt=schedule_input.start_dt_norm,
        end_date=schedule_input.end_date_norm,
        batches=schedule_input.batches,
        operations=schedule_input.operations,
        results=optimizer_outcome.results,
        summary=optimizer_outcome.summary,
        used_strategy=optimizer_outcome.used_strategy,
        used_params=optimizer_outcome.used_params,
        algo_mode=optimizer_outcome.algo_mode,
        objective_name=optimizer_outcome.objective_name,
        time_budget_seconds=int(optimizer_outcome.time_budget_seconds),
        best_score=optimizer_outcome.best_score,
        best_metrics=optimizer_outcome.best_metrics,
        best_order=optimizer_outcome.best_order,
        attempts=optimizer_outcome.attempts,
        improvement_trace=optimizer_outcome.improvement_trace,
        frozen_op_ids=set(schedule_input.frozen_op_ids),
        missing_internal_resource_op_ids=set(schedule_input.missing_internal_resource_op_ids or set()),
        scheduled_op_ids=set(validated_schedule_payload.scheduled_op_ids),
        freeze_meta=schedule_input.freeze_meta,
        input_build_outcome=schedule_input.algo_input_outcome,
        downtime_meta=schedule_input.downtime_meta,
        resource_pool_meta=schedule_input.resource_pool_meta,
        readiness_gate_enabled=bool(schedule_input.readiness_gate_enabled),
        algo_stats=optimizer_outcome.algo_stats,
        algo_warnings=list(schedule_input.algo_warnings or []),
        warning_merge_status=warning_merge_status,
        graph_analysis_public=graph_analysis_public,
        graph_analysis_diagnostics=graph_analysis_diagnostics,
        candidate_comparison_public=(
            candidate_comparison_public_summary(candidate_comparison)
            if candidate_comparison is not None
            else None
        ),
        simulate=simulate,
        t0=schedule_input.t0,
    )

    overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary_fn(
        svc,
        ctx=summary_ctx,
    )

    return ScheduleOrchestrationOutcome(
        version=version,
        results=optimizer_outcome.results,
        summary=optimizer_outcome.summary,
        summary_contract=_build_summary_contract(
            optimizer_outcome.summary,
            result_summary_obj=result_summary_obj,
        ),
        validated_schedule_payload=validated_schedule_payload,
        used_strategy=optimizer_outcome.used_strategy,
        used_params=optimizer_outcome.used_params,
        best_metrics=optimizer_outcome.best_metrics,
        best_score=optimizer_outcome.best_score,
        best_order=optimizer_outcome.best_order,
        attempts=optimizer_outcome.attempts,
        improvement_trace=optimizer_outcome.improvement_trace,
        algo_mode=optimizer_outcome.algo_mode,
        objective_name=optimizer_outcome.objective_name,
        algo_stats=optimizer_outcome.algo_stats,
        time_budget_seconds=optimizer_outcome.time_budget_seconds,
        warning_merge_status=warning_merge_status,
        algo_warnings=list(schedule_input.algo_warnings or []),
        overdue_items=overdue_items,
        result_status=result_status,
        result_summary_obj=result_summary_obj,
        result_summary_json=result_summary_json,
        time_cost_ms=int(time_cost_ms),
        candidate_comparison=candidate_comparison,
    )
