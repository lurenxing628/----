"""Optimizer result contracts and measured baseline output construction."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_runtime import OptimizerRuntime
from .optimizer_search_budget import OptimizerPhaseBudget, SearchBudget, publish_search_budget
from .optimizer_search_report import OptimizationSearchReportState
from .optimizer_search_state import OptimizerSearchState


@dataclass
class OptimizationOutcome:
    results: List[ScheduleResult]
    summary: Any  # ScheduleSummary（来自算法模块；保持与现有代码兼容）
    used_strategy: SortStrategy
    used_params: Dict[str, Any]
    metrics: Any  # ScheduleMetrics
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    algo_stats: Dict[str, Any] = field(default_factory=dict)
    search_report: Dict[str, Any] = field(default_factory=dict)
    # Dispatch mode and rule of the adopted plan; the rule may differ from the configured one
    # because multi-start and the rule neighborhood search the whole rule pool.
    dispatch_mode: str = ""
    dispatch_rule: str = ""


def _runtime_ms(runtime: OptimizerRuntime, *, t_begin: float) -> int:
    elapsed = float(runtime.clock() - t_begin)
    return max(int(elapsed * 1000), 0)


def _baseline_candidate(
    *,
    results: List[ScheduleResult],
    summary: Any,
    used_strategy: SortStrategy,
    used_params: Dict[str, Any],
    dispatch_mode: str,
    dispatch_rule: str,
    best_order: List[str],
    best_metrics: Any,
    best_score: Tuple[float, ...],
    algo_stats: Dict[str, Any],
    resource_pool: Optional[Dict[str, Any]],
    seed_sr_list: List[ScheduleResult],
) -> Dict[str, Any]:
    return {
        "results": results,
        "summary": summary,
        "strategy": used_strategy,
        "params": dict(used_params or {}),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": list(best_order or []),
        "metrics": best_metrics,
        "score": tuple(best_score or ()),
        "algo_stats": algo_stats,
        "resource_pool": resource_pool or {},
        "seed_result_count": len(seed_sr_list or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(seed_sr_list or [])],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(best_order or [])},
    }


def _baseline_outcome(
    *,
    runtime: OptimizerRuntime,
    optimizer_cfg: Any,
    optimizer_algo_stats: Dict[str, Any],
    state: OptimizerSearchState,
    search_report_state: OptimizationSearchReportState,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Optional[Any],
    build_order: Any,
    t_begin: float,
    search_budget: Optional[SearchBudget],
    phases: OptimizerPhaseBudget,
    schedule_fn: Any,
) -> OptimizationOutcome:
    results, summary, used_strategy, used_params = schedule_fn(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=optimizer_cfg.strategy_enum,
        strategy_params=optimizer_cfg.strategy_params,
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        seed_results=seed_sr_list,
        dispatch_mode=dispatch_mode_cfg,
        resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_ready_context=graph_ready_context,
    )
    best_metrics = compute_metrics(
        results, batches, expected_operations=algo_ops_to_schedule,
        seed_results=seed_sr_list, failure_details=getattr(summary, "failure_details", ()),
    )
    best_score = (float(summary.failed_ops),) + objective_score(optimizer_cfg.objective_name, best_metrics)
    best_order = build_order(optimizer_cfg.strategy_enum or SortStrategy.PRIORITY_FIRST, used_params or {})
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    baseline = _baseline_candidate(
        results=results,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        dispatch_mode=dispatch_mode_cfg,
        dispatch_rule=optimizer_cfg.dispatch_rule,
        best_order=best_order,
        best_metrics=best_metrics,
        best_score=best_score,
        algo_stats=algo_stats,
        resource_pool=resource_pool,
        seed_sr_list=seed_sr_list,
    )
    search_report_state.mark_candidate_evaluated(baseline, origin="baseline")
    search_report_state.mark_candidate_accepted(baseline, origin="baseline")
    publish_search_budget(
        report_state=search_report_state, attempts=state.attempts, budget=search_budget,
        phases=phases, started_at=t_begin, finished_at=runtime.clock(),
    )
    compacted_attempts = state.compact_attempts(limit=12)
    compacted_trace = state.compact_trace(limit=200)
    search_report = search_report_state.finalize(
        runtime_ms=_runtime_ms(runtime, t_begin=t_begin),
        attempts=compacted_attempts,
        improvement_trace=compacted_trace,
        stop_reason="time_budget" if search_report_state.deadline_reached else "baseline_scheduled",
    )
    _record_decoder_invocations(search_report, scheduler)
    return OptimizationOutcome(
        results=results,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        metrics=best_metrics,
        best_score=best_score,
        best_order=best_order,
        attempts=compacted_attempts,
        improvement_trace=compacted_trace,
        algo_mode=optimizer_cfg.algo_mode,
        objective_name=optimizer_cfg.objective_name,
        time_budget_seconds=optimizer_cfg.time_budget_seconds,
        algo_stats=algo_stats,
        search_report=search_report,
        dispatch_mode=str(dispatch_mode_cfg),
        dispatch_rule=str(optimizer_cfg.dispatch_rule),
    )


def _record_decoder_invocations(report: Dict[str, Any], scheduler: Any) -> None:
    if not isinstance(scheduler, GreedyScheduler):
        return
    value = vars(scheduler).get("_decode_invocations")
    if type(value) is int and value >= 0:
        report["decoder_invocations"] = value
