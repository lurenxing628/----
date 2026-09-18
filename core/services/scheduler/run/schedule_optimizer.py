from __future__ import annotations

import random
import time
from dataclasses import replace
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.ordering import build_batch_sort_inputs, build_normalized_batches_map
from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.greedy.algo_stats import merge_algo_stats
from core.infrastructure.errors import ValidationError

from .optimizer_candidate_phases import run_heuristic_candidate_phases
from .optimizer_candidate_profile import build_candidate_profile
from .optimizer_config import ensure_optimizer_config_snapshot, is_ortools_enabled, resolve_optimizer_config
from .optimizer_graph_ready import run_graph_ready_candidates as _run_graph_ready_candidates_impl
from .optimizer_grasp_ig_candidates import run_grasp_ig_candidates as _run_grasp_ig_candidates_impl
from .optimizer_local_search import run_local_search as _run_local_search_impl
from .optimizer_outcome import OptimizationOutcome, _baseline_outcome, _record_decoder_invocations, _runtime_ms
from .optimizer_outcome import _baseline_candidate as _baseline_candidate
from .optimizer_runtime import OptimizerRuntime
from .optimizer_search_budget import (
    OptimizerPhaseBudget,
    ReservedPhaseReport,
    SearchBudget,
    SearchBudgetExhausted,
    publish_search_budget,
)
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


def _run_local_search(**kwargs):
    kwargs.setdefault("clock", time.time)
    kwargs.setdefault("rng_factory", random.Random)
    kwargs.setdefault("schedule_fn", _schedule_with_optional_strict_mode)
    kwargs.setdefault("readiness_gate_enabled", False)
    return _run_local_search_impl(**kwargs)


def _run_grasp_ig_candidates(**kwargs):
    kwargs.setdefault("schedule_fn", _schedule_with_optional_strict_mode)
    return _run_grasp_ig_candidates_impl(**kwargs)


def _run_graph_ready_candidates(**kwargs):
    kwargs.setdefault("schedule_fn", _schedule_with_optional_strict_mode)
    return _run_graph_ready_candidates_impl(**kwargs)


def _default_runtime() -> OptimizerRuntime:
    return OptimizerRuntime(
        scheduler_factory=lambda **kwargs: GreedyScheduler(**kwargs),
        clock=time.monotonic,
        rng_factory=random.Random,
        run_ortools_warmstart=_run_ortools_warmstart,
        run_multi_start=_run_multi_start,
        run_graph_ready_candidates=_run_graph_ready_candidates,
        run_grasp_ig_candidates=_run_grasp_ig_candidates,
        run_local_search=_run_local_search,
    )


def _resolve_runtime(runtime: Optional[OptimizerRuntime], search_budget: Optional[SearchBudget]) -> OptimizerRuntime:
    """未显式注入 runtime 时用默认 runtime；有共享搜索预算时改用预算时钟，让各阶段读同一只表。"""
    resolved = runtime or _default_runtime()
    if search_budget is not None:
        resolved = replace(resolved, clock=search_budget.clock)
    return resolved


def _resolve_dispatch_modes(
    optimizer_cfg: Any,
    *,
    graph_ready_context: Optional[Any],
    graph_dispatch_mode_override: Optional[str],
) -> Tuple[bool, str, List[str]]:
    """带图就绪上下文或显式覆盖为 sgs 时只跑 sgs，否则沿用配置；返回 (是否强制 sgs, 主派工模式, 待尝试模式列表)。"""
    graph_sgs_required = graph_ready_context is not None or graph_dispatch_mode_override == "sgs"
    dispatch_mode_cfg = "sgs" if graph_sgs_required else optimizer_cfg.dispatch_mode
    dispatch_modes = ["sgs"] if graph_sgs_required else optimizer_cfg.dispatch_modes()
    return graph_sgs_required, dispatch_mode_cfg, dispatch_modes


def _resolve_deadline(optimizer_cfg: Any, *, t_begin: float, search_budget: Optional[SearchBudget]) -> float:
    """improve 模式按配置预算算截止时刻，其他模式不设限；有共享预算时以预算裁定的截止时刻为准。"""
    improve = optimizer_cfg.algo_mode == "improve"
    deadline = (t_begin + float(optimizer_cfg.time_budget_seconds)) if improve else float("inf")
    if search_budget is not None:
        deadline = search_budget.optimizer_deadline(
            started_at=t_begin, configured_seconds=optimizer_cfg.time_budget_seconds, improve=improve,
        )
    return deadline


def _merge_best_algo_stats(best: Dict[str, Any], optimizer_algo_stats: Dict[str, Any]) -> Dict[str, Any]:
    """最优解自带 algo_stats 时以它为准，否则合并优化器层累计的统计。"""
    best_algo_stats = best.get("algo_stats") if isinstance(best, dict) else None
    if isinstance(best_algo_stats, dict):
        return merge_algo_stats(best_algo_stats)
    return merge_algo_stats(optimizer_algo_stats)


def _best_outcome(
    *,
    runtime: OptimizerRuntime,
    optimizer_cfg: Any,
    optimizer_algo_stats: Dict[str, Any],
    state: OptimizerSearchState,
    best: Dict[str, Any],
    search_report_state: OptimizationSearchReportState,
    scheduler: Any,
    dispatch_mode_cfg: str,
    t_begin: float,
    search_budget: Optional[SearchBudget],
    phases: OptimizerPhaseBudget,
) -> OptimizationOutcome:
    """搜索已产出最优解：发布最终预算、压缩尝试与改进轨迹、定稿搜索报告并封装为 OptimizationOutcome。"""
    results = best["results"]
    summary = best["summary"]
    used_strategy = best["strategy"]
    used_params = best["params"]
    best_metrics = best["metrics"]
    best_score = best["score"]
    best_order = best["order"]
    algo_stats = _merge_best_algo_stats(best, optimizer_algo_stats)
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
    )
    _record_decoder_invocations(search_report, scheduler)
    adopted_mode = str(best.get("dispatch_mode") or dispatch_mode_cfg)
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
        dispatch_mode=adopted_mode,
        dispatch_rule=_adopted_dispatch_rule(best, adopted_mode=adopted_mode, configured_rule=optimizer_cfg.dispatch_rule),
    )


def _adopted_dispatch_rule(best: Dict[str, Any], *, adopted_mode: str, configured_rule: str) -> str:
    """Only an sgs decode consumes the rule; any other mode adopted exactly the configured rule."""
    if adopted_mode != "sgs":
        return str(configured_rule)
    return str(best.get("dispatch_rule") or configured_rule)


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
    search_budget: Optional[SearchBudget] = None,
    _runtime: Optional[OptimizerRuntime] = None,
) -> OptimizationOutcome:
    """
    执行算法（支持 improve：多起点 + 目标函数 + 时间预算；可选 OR-Tools 起点）。

    说明：本入口仍是服务主链到算法核心的合同保护层；配置、seed 与搜索执行已拆到窄职责模块。
    """
    runtime = _resolve_runtime(_runtime, search_budget)
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
    graph_sgs_required, dispatch_mode_cfg, dispatch_modes = _resolve_dispatch_modes(
        optimizer_cfg,
        graph_ready_context=graph_ready_context,
        graph_dispatch_mode_override=graph_dispatch_mode_override,
    )
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
    deadline = _resolve_deadline(optimizer_cfg, t_begin=t_begin, search_budget=search_budget)
    phases = OptimizerPhaseBudget.create(
        started_at=t_begin, deadline=deadline, improve=optimizer_cfg.algo_mode == "improve",
        graph_ready=graph_ready_context is not None,
    )
    search_report_state = OptimizationSearchReportState(
        algorithm_profile=candidate_profile.profile,
        seed=int(version),
        time_budget_seconds=int(optimizer_cfg.time_budget_seconds),
        objective_name=str(optimizer_cfg.objective_name),
        started_at=float(t_begin),
        strict_mode=bool(strict_mode),
        candidate_profile=candidate_profile.to_report_dict(),
    )
    publish_search_budget(
        report_state=search_report_state, attempts=state.attempts, budget=search_budget,
        phases=phases, started_at=t_begin,
    )
    if runtime.clock() >= deadline:
        raise SearchBudgetExhausted("candidate_time_budget_reached")

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
        phase_deadline=phases.multi_start_deadline,
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

    state.best = runtime.run_ortools_warmstart(
        algo_mode=optimizer_cfg.algo_mode, cfg=cfg, strategy_enum=optimizer_cfg.strategy_enum,
        objective_name=optimizer_cfg.objective_name, deadline=phases.warmstart_deadline,
        scheduler=scheduler, algo_ops_to_schedule=algo_ops_to_schedule, batches=batches,
        start_dt=start_dt, end_date=end_date, downtime_map=downtime_map, seed_sr_list=seed_sr_list,
        dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        resource_pool=resource_pool, attempts=state.attempts, improvement_trace=state.improvement_trace,
        best=state.best, optimizer_algo_stats=optimizer_algo_stats, t_begin=t_begin, logger=logger,
        readiness_gate_enabled=bool(readiness_gate_enabled), strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context, clock=runtime.clock,
        search_report_state=ReservedPhaseReport(
            search_report_state, clock=runtime.clock, deadline=deadline, phase="ortools_warmstart",
        ),
    )

    state.best = run_heuristic_candidate_phases(
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
        deadline=phases.heuristic_deadline,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        search_report_state=cast(Any, ReservedPhaseReport(
            search_report_state, clock=runtime.clock, deadline=deadline, phase="heuristic_candidate_search",
        )),
        schedule_fn=_schedule_with_optional_strict_mode,
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
        valid_dispatch_rules=list(optimizer_cfg.valid_dispatch_rules),
        acceptance=candidate_profile.acceptance,
    )

    if state.best is None:
        if runtime.clock() >= deadline:
            raise SearchBudgetExhausted("candidate_time_budget_reached")
        return _baseline_outcome(
            runtime=runtime,
            optimizer_cfg=optimizer_cfg,
            optimizer_algo_stats=optimizer_algo_stats,
            state=state,
            search_report_state=search_report_state,
            scheduler=scheduler,
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            seed_sr_list=seed_sr_list,
            dispatch_mode_cfg=dispatch_mode_cfg,
            resource_pool=resource_pool,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            strict_mode=bool(strict_mode),
            graph_ready_context=graph_ready_context,
            build_order=_build_order,
            t_begin=t_begin,
            search_budget=search_budget,
            phases=phases,
            schedule_fn=_schedule_with_optional_strict_mode,
        )

    return _best_outcome(
        runtime=runtime,
        optimizer_cfg=optimizer_cfg,
        optimizer_algo_stats=optimizer_algo_stats,
        state=state,
        best=state.best,
        search_report_state=search_report_state,
        scheduler=scheduler,
        dispatch_mode_cfg=dispatch_mode_cfg,
        t_begin=t_begin,
        search_budget=search_budget,
        phases=phases,
    )
