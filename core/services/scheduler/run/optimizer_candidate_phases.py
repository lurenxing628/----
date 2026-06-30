from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult

from .optimizer_runtime import OptimizerRuntime
from .optimizer_search_report import OptimizationSearchReportState
from .optimizer_search_state import OptimizerSearchState


def run_heuristic_candidate_phases(
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
    schedule_fn: Any,
) -> Optional[Dict[str, Any]]:
    state.best = _run_graph_ready_candidate_phase(
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
        build_order=build_order,
        resource_pool=resource_pool,
        deadline=deadline,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=readiness_gate_enabled,
        strict_mode=strict_mode,
        graph_ready_context=graph_ready_context,
        search_report_state=search_report_state,
        schedule_fn=schedule_fn,
    )
    return _run_grasp_ig_candidate_phase(
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
        build_order=build_order,
        dispatch_modes=dispatch_modes,
        resource_pool=resource_pool,
        deadline=deadline,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=readiness_gate_enabled,
        strict_mode=strict_mode,
        graph_ready_context=graph_ready_context,
        search_report_state=search_report_state,
        schedule_fn=schedule_fn,
    )


def _run_graph_ready_candidate_phase(**kwargs: Any) -> Optional[Dict[str, Any]]:
    runtime = kwargs["runtime"]
    if runtime.run_graph_ready_candidates is None:
        return kwargs["state"].best
    optimizer_cfg = kwargs["optimizer_cfg"]
    candidate_profile = kwargs["candidate_profile"]
    return runtime.run_graph_ready_candidates(
        algo_mode=optimizer_cfg.algo_mode,
        best=kwargs["state"].best,
        version=int(candidate_profile.seed),
        scheduler=kwargs["scheduler"],
        algo_ops_to_schedule=kwargs["algo_ops_to_schedule"],
        batches=kwargs["batches"],
        start_dt=kwargs["start_dt"],
        end_date=kwargs["end_date"],
        downtime_map=kwargs["downtime_map"],
        seed_sr_list=kwargs["seed_sr_list"],
        base_strategy=optimizer_cfg.strategy_enum,
        base_params=dict(optimizer_cfg.strategy_params or {}),
        build_order=kwargs["build_order"],
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        resource_pool=kwargs["resource_pool"],
        objective_name=optimizer_cfg.objective_name,
        deadline=kwargs["deadline"],
        attempts=kwargs["state"].attempts,
        improvement_trace=kwargs["state"].improvement_trace,
        optimizer_algo_stats=kwargs["optimizer_algo_stats"],
        t_begin=kwargs["t_begin"],
        readiness_gate_enabled=bool(kwargs["readiness_gate_enabled"]),
        strict_mode=bool(kwargs["strict_mode"]),
        graph_ready_context=kwargs["graph_ready_context"],
        clock=runtime.clock,
        schedule_fn=kwargs["schedule_fn"],
        search_report_state=kwargs["search_report_state"],
        candidate_construction=dict(candidate_profile.candidate_construction or {}),
    )


def _run_grasp_ig_candidate_phase(**kwargs: Any) -> Optional[Dict[str, Any]]:
    runtime = kwargs["runtime"]
    if runtime.run_grasp_ig_candidates is None:
        return kwargs["state"].best
    optimizer_cfg = kwargs["optimizer_cfg"]
    candidate_profile = kwargs["candidate_profile"]
    return runtime.run_grasp_ig_candidates(
        algo_mode=optimizer_cfg.algo_mode,
        best=kwargs["state"].best,
        version=int(candidate_profile.seed),
        candidate_construction=dict(candidate_profile.candidate_construction or {}),
        scheduler=kwargs["scheduler"],
        algo_ops_to_schedule=kwargs["algo_ops_to_schedule"],
        batches=kwargs["batches"],
        start_dt=kwargs["start_dt"],
        end_date=kwargs["end_date"],
        downtime_map=kwargs["downtime_map"],
        seed_sr_list=kwargs["seed_sr_list"],
        base_strategy=optimizer_cfg.strategy_enum,
        base_params=dict(optimizer_cfg.strategy_params or {}),
        build_order=kwargs["build_order"],
        dispatch_rule_cfg=optimizer_cfg.dispatch_rule,
        valid_dispatch_rules=list(optimizer_cfg.valid_dispatch_rules),
        batch_order_enabled="batch_order" in set(kwargs["dispatch_modes"]),
        resource_pool=kwargs["resource_pool"],
        objective_name=optimizer_cfg.objective_name,
        deadline=kwargs["deadline"],
        attempts=kwargs["state"].attempts,
        improvement_trace=kwargs["state"].improvement_trace,
        optimizer_algo_stats=kwargs["optimizer_algo_stats"],
        t_begin=kwargs["t_begin"],
        readiness_gate_enabled=bool(kwargs["readiness_gate_enabled"]),
        strict_mode=bool(kwargs["strict_mode"]),
        graph_ready_context=kwargs["graph_ready_context"],
        clock=runtime.clock,
        rng_factory=runtime.rng_factory,
        schedule_fn=kwargs["schedule_fn"],
        search_report_state=kwargs["search_report_state"],
    )
