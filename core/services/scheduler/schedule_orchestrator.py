from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .schedule_input_collector import ScheduleRunInput, _raise_schedule_empty_result


@dataclass
class ScheduleOrchestrationOutcome:
    version: int
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
    has_actionable_schedule: bool
    warning_merge_status: Dict[str, Any]
    algo_warnings: List[str]
    overdue_items: List[Any]
    result_status: str
    result_summary_obj: Dict[str, Any]
    result_summary_json: str
    time_cost_ms: int


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


def _normalize_optimizer_outcome(optimizer_outcome: Any) -> _NormalizedOptimizerOutcome:
    return _NormalizedOptimizerOutcome(
        results=list(getattr(optimizer_outcome, "results", []) or []),
        summary=getattr(optimizer_outcome, "summary", None),
        used_strategy=getattr(optimizer_outcome, "used_strategy", None),
        used_params=dict(getattr(optimizer_outcome, "used_params", {}) or {}),
        best_metrics=getattr(optimizer_outcome, "metrics", None),
        best_score=tuple(getattr(optimizer_outcome, "best_score", ()) or ()),
        best_order=list(getattr(optimizer_outcome, "best_order", []) or []),
        attempts=list(getattr(optimizer_outcome, "attempts", []) or []),
        improvement_trace=list(getattr(optimizer_outcome, "improvement_trace", []) or []),
        algo_mode=str(getattr(optimizer_outcome, "algo_mode", "") or ""),
        objective_name=str(getattr(optimizer_outcome, "objective_name", "") or ""),
        algo_stats=dict(getattr(optimizer_outcome, "algo_stats", {}) or {}),
        time_budget_seconds=int(getattr(optimizer_outcome, "time_budget_seconds", 0) or 0),
    )


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
                warning_merge_status["summary_merge_error"] = str(exc)

    if algo_warnings:
        if hasattr(summary_warnings, "extend"):
            summary_warnings.extend(algo_warnings)
        else:
            warning_merge_status["summary_merge_failed"] = True
            warning_merge_status["summary_merge_error"] = (
                warning_merge_status.get("summary_merge_error") or "summary_warnings_unavailable"
            )

    return warning_merge_status


def orchestrate_schedule_run(
    svc: Any,
    *,
    schedule_input: ScheduleRunInput,
    simulate: bool,
    strict_mode: bool,
    optimize_schedule_fn: Any,
    has_actionable_schedule_rows_fn: Any,
    build_result_summary_fn: Any,
) -> ScheduleOrchestrationOutcome:
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
            logger=svc.logger,
            strict_mode=bool(strict_mode),
        )
    )

    has_actionable_schedule = bool(
        has_actionable_schedule_rows_fn(optimizer_outcome.results, allowed_op_ids=set(schedule_input.reschedulable_op_ids))
    )
    if not has_actionable_schedule:
        _raise_schedule_empty_result(
            f"优化结果未生成有效可落库排程行，本次未执行{schedule_input.run_label}。",
            reason="no_actionable_schedule_rows",
        )

    warning_merge_status = _merge_summary_warnings(
        optimizer_outcome.summary,
        list(schedule_input.algo_warnings or []),
    )

    with svc.tx_manager.transaction():
        version = int(svc.history_repo.allocate_next_version())

    overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary_fn(
        svc,
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
        freeze_meta=schedule_input.freeze_meta,
        input_build_outcome=schedule_input.algo_input_outcome,
        downtime_meta=schedule_input.downtime_meta,
        resource_pool_meta=schedule_input.resource_pool_meta,
        algo_stats=optimizer_outcome.algo_stats,
        algo_warnings=list(schedule_input.algo_warnings or []),
        warning_merge_status=warning_merge_status,
        simulate=simulate,
        t0=schedule_input.t0,
    )

    return ScheduleOrchestrationOutcome(
        version=version,
        results=optimizer_outcome.results,
        summary=optimizer_outcome.summary,
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
        has_actionable_schedule=has_actionable_schedule,
        warning_merge_status=warning_merge_status,
        algo_warnings=list(schedule_input.algo_warnings or []),
        overdue_items=overdue_items,
        result_status=result_status,
        result_summary_obj=result_summary_obj,
        result_summary_json=result_summary_json,
        time_cost_ms=int(time_cost_ms),
    )
