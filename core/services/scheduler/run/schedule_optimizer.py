from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats
from core.algorithms.ordering import build_batch_sort_inputs, build_normalized_batches_map
from core.infrastructure.errors import ValidationError

from .optimizer_candidate_profile import build_candidate_profile
from .optimizer_config import ensure_optimizer_config_snapshot, is_ortools_enabled, resolve_optimizer_config
from .optimizer_grasp_ig_candidates import run_grasp_ig_candidates as _run_grasp_ig_candidates_impl
from .optimizer_local_search import run_local_search as _run_local_search_impl
from .optimizer_runtime import OptimizerRuntime
from .optimizer_search_report import OptimizationSearchReportState
from .optimizer_search_state import (
    OptimizerSearchState,
)
from .optimizer_search_state import (
    compact_attempts as _compact_attempts,
)
from .optimizer_search_state import (
    score_tuple as _score_tuple,
)
from .schedule_optimizer_steps import (
    _run_multi_start,
    _run_ortools_warmstart,
    _schedule_with_optional_strict_mode,
)
from .schedule_seed_contracts import coerce_seed_results as _coerce_seed_results


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


def _run_local_search(**kwargs):
    kwargs.setdefault("clock", time.time)
    kwargs.setdefault("rng_factory", random.Random)
    kwargs.setdefault("schedule_fn", _schedule_with_optional_strict_mode)
    kwargs.setdefault("readiness_gate_enabled", False)
    return _run_local_search_impl(**kwargs)


def _run_grasp_ig_candidates(**kwargs):
    kwargs.setdefault("schedule_fn", _schedule_with_optional_strict_mode)
    return _run_grasp_ig_candidates_impl(**kwargs)


def _default_runtime() -> OptimizerRuntime:
    return OptimizerRuntime(
        scheduler_factory=lambda **kwargs: GreedyScheduler(**kwargs),
        clock=time.time,
        rng_factory=random.Random,
        run_ortools_warmstart=_run_ortools_warmstart,
        run_multi_start=_run_multi_start,
        run_grasp_ig_candidates=_run_grasp_ig_candidates,
        run_local_search=_run_local_search,
    )


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


def _run_grasp_ig_candidate_phase(
    *,
    runtime: OptimizerRuntime,
    optimizer_cfg: Any,
    candidate_profile: Any,
    state: OptimizerSearchState,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    build_order: Any,
    dispatch_modes: List[str],
    resource_pool: Optional[Dict[str, Any]],
    deadline: float,
    optimizer_algo_stats: Dict[str, Any],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Optional[Any],
    search_report_state: OptimizationSearchReportState,
) -> Optional[Dict[str, Any]]:
    if runtime.run_grasp_ig_candidates is None:
        return state.best
    return runtime.run_grasp_ig_candidates(
        algo_mode=optimizer_cfg.algo_mode,
        best=state.best,
        version=int(candidate_profile.seed),
        candidate_construction=dict(candidate_profile.candidate_construction or {}),
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        base_strategy=optimizer_cfg.strategy_enum,
        base_params=dict(optimizer_cfg.strategy_params or {}),
        build_order=build_order,
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        valid_dispatch_rules=list(optimizer_cfg.valid_dispatch_rules),
        sgs_enabled="sgs" in set(dispatch_modes),
        resource_pool=resource_pool,
        objective_name=optimizer_cfg.objective_name,
        deadline=deadline,
        attempts=state.attempts,
        improvement_trace=state.improvement_trace,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        clock=runtime.clock,
        rng_factory=runtime.rng_factory,
        schedule_fn=_schedule_with_optional_strict_mode,
        search_report_state=search_report_state,
    )


def optimize_schedule(
    *,
    calendar_service: Any,
    cfg_svc: Any,
    cfg: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results: List[Dict[str, Any]],
    resource_pool: Optional[Dict[str, Any]],
    version: int,
    logger: Any = None,
    readiness_gate_enabled: bool = False,
    strict_mode: bool = False,
    graph_ready_context: Optional[Any] = None,
    graph_dispatch_mode_override: Optional[str] = None,
    _runtime: Optional[OptimizerRuntime] = None,
) -> OptimizationOutcome:
    """
    执行算法（支持 improve：多起点 + 目标函数 + 时间预算；可选 OR-Tools 起点）。

    说明：本入口仍是服务主链到算法核心的合同保护层；配置、seed 与搜索执行已拆到窄职责模块。
    """
    runtime = _runtime or _default_runtime()
    optimizer_algo_stats: Dict[str, Any] = {"fallback_counts": {}, "param_fallbacks": {}}
    cfg = ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))
    if graph_dispatch_mode_override not in (None, "sgs"):
        raise ValidationError("图派工模式覆盖只允许使用 sgs。", field="graph_dispatch_mode_override")

    # 保持原有顺序：strict 配置快照错误先于 seed 错误；allowlist 解析仍在 seed 边界之后。
    seed_sr_list = _coerce_seed_results(seed_results, optimizer_algo_stats=optimizer_algo_stats)
    scheduler = runtime.scheduler_factory(calendar_service=calendar_service, config_service=cfg, logger=logger)
    optimizer_cfg = resolve_optimizer_config(
        cfg_svc=cfg_svc,
        snapshot=cfg,
        optimizer_algo_stats=optimizer_algo_stats,
        strict_mode=bool(strict_mode),
    )
    graph_sgs_required = graph_ready_context is not None or graph_dispatch_mode_override == "sgs"
    dispatch_mode_cfg = "sgs" if graph_sgs_required else optimizer_cfg.dispatch_mode
    dispatch_modes = ["sgs"] if graph_sgs_required else optimizer_cfg.dispatch_modes()
    candidate_profile = build_candidate_profile(
        algo_mode=optimizer_cfg.algo_mode,
        dispatch_mode=optimizer_cfg.dispatch_mode,
        dispatch_rule=optimizer_cfg.dispatch_rule,
        time_budget_seconds=optimizer_cfg.time_budget_seconds,
        version=version,
        strict_mode=bool(strict_mode),
        ortools_enabled=is_ortools_enabled(cfg),
        graph_sgs_required=graph_sgs_required,
    )

    normalized_batches_for_sort = build_normalized_batches_map(batches)

    def _build_order(strategy0: SortStrategy, params: Dict[str, Any]) -> List[str]:
        batch_for_sort = build_batch_sort_inputs(
            normalized_batches_for_sort,
            strict_mode=bool(strict_mode),
            strategy=strategy0,
            readiness_gate_enabled=bool(readiness_gate_enabled),
        )
        sorter0 = StrategyFactory.create(strategy0, **(params or {}))
        return [item.batch_id for item in sorter0.sort(batch_for_sort, base_date=start_dt.date())]

    state = OptimizerSearchState()
    t_begin = runtime.clock()
    deadline = (t_begin + float(optimizer_cfg.time_budget_seconds)) if optimizer_cfg.algo_mode == "improve" else float("inf")
    search_report_state = OptimizationSearchReportState(
        algorithm_profile=candidate_profile.profile,
        seed=int(version),
        time_budget_seconds=int(optimizer_cfg.time_budget_seconds),
        objective_name=str(optimizer_cfg.objective_name),
        started_at=float(t_begin),
        strict_mode=bool(strict_mode),
        candidate_profile=candidate_profile.to_report_dict(),
    )

    state.best = runtime.run_ortools_warmstart(
        algo_mode=optimizer_cfg.algo_mode,
        cfg=cfg,
        strategy_enum=optimizer_cfg.strategy_enum,
        objective_name=optimizer_cfg.objective_name,
        deadline=deadline,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        dispatch_mode_cfg=dispatch_mode_cfg,
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        resource_pool=resource_pool,
        attempts=state.attempts,
        improvement_trace=state.improvement_trace,
        best=state.best,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        logger=logger,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        clock=runtime.clock,
        search_report_state=search_report_state,
    )

    state.best = runtime.run_multi_start(
        keys=optimizer_cfg.strategy_keys(),
        dispatch_modes=dispatch_modes,
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        valid_dispatch_rules=list(optimizer_cfg.valid_dispatch_rules),
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        cfg=cfg,
        resource_pool=resource_pool,
        objective_name=optimizer_cfg.objective_name,
        deadline=deadline,
        attempts=state.attempts,
        improvement_trace=state.improvement_trace,
        best=state.best,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        build_order=_build_order,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        clock=runtime.clock,
        search_report_state=search_report_state,
    )

    state.best = _run_grasp_ig_candidate_phase(
        runtime=runtime,
        optimizer_cfg=optimizer_cfg,
        candidate_profile=candidate_profile,
        state=state,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        build_order=_build_order,
        dispatch_modes=dispatch_modes,
        resource_pool=resource_pool,
        deadline=deadline,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        search_report_state=search_report_state,
    )

    state.best = runtime.run_local_search(
        algo_mode=optimizer_cfg.algo_mode,
        best=state.best,
        version=version,
        time_budget_seconds=optimizer_cfg.time_budget_seconds,
        deadline=deadline,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        dispatch_mode_cfg=dispatch_mode_cfg,
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        resource_pool=resource_pool,
        objective_name=optimizer_cfg.objective_name,
        attempts=state.attempts,
        improvement_trace=state.improvement_trace,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        clock=runtime.clock,
        rng_factory=runtime.rng_factory,
        schedule_fn=_schedule_with_optional_strict_mode,
        search_report_state=search_report_state,
        neighborhoods=tuple(candidate_profile.neighborhoods),
        acceptance=candidate_profile.acceptance,
    )

    if state.best is None:
        results, summary, used_strategy, used_params = _schedule_with_optional_strict_mode(
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
        best_metrics = compute_metrics(results, batches)
        best_score = (float(summary.failed_ops),) + objective_score(optimizer_cfg.objective_name, best_metrics)
        best_order = _build_order(optimizer_cfg.strategy_enum or SortStrategy.PRIORITY_FIRST, used_params or {})
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
        compacted_attempts = state.compact_attempts(limit=12)
        compacted_trace = state.compact_trace(limit=200)
        search_report = search_report_state.finalize(
            runtime_ms=_runtime_ms(runtime, t_begin=t_begin),
            attempts=compacted_attempts,
            improvement_trace=compacted_trace,
            stop_reason="baseline_scheduled",
        )
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
        )

    best = state.best
    results = best["results"]
    summary = best["summary"]
    used_strategy = best["strategy"]
    used_params = best["params"]
    best_metrics = best["metrics"]
    best_score = best["score"]
    best_order = best["order"]
    best_algo_stats = best.get("algo_stats") if isinstance(best, dict) else None
    algo_stats = merge_algo_stats(best_algo_stats) if isinstance(best_algo_stats, dict) else merge_algo_stats(optimizer_algo_stats)
    compacted_attempts = state.compact_attempts(limit=12)
    compacted_trace = state.compact_trace(limit=200)
    search_report = search_report_state.finalize(
        runtime_ms=_runtime_ms(runtime, t_begin=t_begin),
        attempts=compacted_attempts,
        improvement_trace=compacted_trace,
    )

    return OptimizationOutcome(
        results=results,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        metrics=best_metrics,
        best_score=best_score,
        best_order=list(best_order or []),
        attempts=compacted_attempts,
        improvement_trace=compacted_trace,
        algo_mode=optimizer_cfg.algo_mode,
        objective_name=optimizer_cfg.objective_name,
        time_budget_seconds=optimizer_cfg.time_budget_seconds,
        algo_stats=algo_stats,
        search_report=search_report,
    )
