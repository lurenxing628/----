from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.search_stage import SearchStage

from .budget import GraphReadySearchBudget
from .candidates import PreparedDecisionFeatures, build_v2_common_rank_cache, evaluate_graph_ready_candidate
from .context import graph_node_metrics_by_op_id, validate_graph_ready_context
from .iterated_greedy_contract import IteratedGreedyLimits, resolve_iterated_greedy_limits
from .iterated_greedy_run import IteratedGreedyRun
from .predecode import GraphReadyProfileSearch
from .profile_selection import resolve_graph_ready_profiles_and_metrics
from .repair import EliteRepairPool, EliteRepairRun
from .repair_contract import EliteRepairLimits, resolve_elite_repair_limits
from .stages import GraphSearchState, IteratedGreedyStage, ProfileStage, RepairStage, iterated_greedy_parent_profile
from .v2_features import enrich_graph_ready_v2_metrics

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession


class GraphReadyDeadlineExhausted(RuntimeError):
    pass


@dataclass
class SharedGraphFeatures:
    """One prepared, objective-independent feature set for a shared search."""

    metrics_by_op_id: Dict[int, Dict[str, Any]]
    v2_common_rank_cache: Dict[str, Dict[int, float]]
    decision_features: PreparedDecisionFeatures = field(init=False)

    def __post_init__(self) -> None:
        self.decision_features = PreparedDecisionFeatures(self.metrics_by_op_id, self.v2_common_rank_cache)


@dataclass
class GraphStageBundle:
    """Graph generators and their stable target view, without a scheduling loop."""

    state: GraphSearchState
    stages: List[SearchStage]

    def finish(self) -> None:
        for stage in self.stages:
            stage.finish()


def prepare_shared_graph_features(
    *, graph_ready_context: Dict[str, Any], scheduler: Any, algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any], start_dt: datetime, downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult], resource_pool: Optional[Dict[str, Any]],
    candidate_construction: Optional[Dict[str, Any]] = None, deadline: Optional[float] = None,
    clock: Optional[Callable[[], float]] = None,
) -> SharedGraphFeatures:
    """Build both existing bases and their ranks once before target stages are assembled."""
    if deadline is not None and clock is not None:
        _before_graph_metrics(construction=candidate_construction, deadline=deadline, clock=clock)
    schedulable_ids = validate_graph_ready_context(graph_ready_context, algo_ops_to_schedule=algo_ops_to_schedule,
                                                  seed_sr_list=seed_sr_list)
    metrics = enrich_graph_ready_v2_metrics(
        graph_node_metrics_by_op_id(graph_ready_context, schedulable_ids=schedulable_ids),
        operations=algo_ops_to_schedule, batches=batches,
        start_dt=start_dt, calendar_service=getattr(scheduler, "calendar", None), downtime_map=downtime_map,
        seed_results=seed_sr_list, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context,
    )
    return SharedGraphFeatures(metrics, build_v2_common_rank_cache(metrics))


def _before_graph_metrics(*, construction: Optional[Dict[str, Any]], deadline: float, clock: Callable[[], float]) -> None:
    # Configuration errors retain fail-loud behavior even with no search time.
    resolve_elite_repair_limits(construction, enabled=False)
    resolve_iterated_greedy_limits(construction, enabled=False)
    if clock() >= deadline:
        raise GraphReadyDeadlineExhausted()


def build_graph_search_stages(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    algo_ops_to_schedule: List[Any],
    start_dt: datetime,
    end_date: Optional[date],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Optional[Any],
    clock: Callable[[], float],
    search_report_state: Optional[OptimizationSearchReportState] = None,
    max_weight_profiles: int = 9,
    candidate_construction: Optional[Dict[str, Any]] = None,
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    skip_reason = _phase_skip_reason(algo_mode=algo_mode, graph_ready_context=graph_ready_context)
    if skip_reason:
        return GraphStageBundle(GraphSearchState(best), [])

    profiles, profile_summary = resolve_graph_ready_profiles_and_metrics(
        max_weight_profiles=max_weight_profiles,
        candidate_construction=candidate_construction,
        version=version,
        objective_name=objective_name,
        shared_search=True,
    )
    repair_limits = resolve_elite_repair_limits(
        candidate_construction,
        enabled=profile_summary.get("candidate_policy") == "objective_aware_portfolio",
    )
    # Iterated greedy shares the incumbent during rotation and follows the repair switch.
    iterated_greedy_limits = resolve_iterated_greedy_limits(candidate_construction, enabled=repair_limits.enabled)
    if clock() >= deadline:
        return GraphStageBundle(GraphSearchState(best), [])
    order = _candidate_order(best, build_order=build_order, base_strategy=base_strategy, base_params=base_params)
    return _build_weight_profile_stages(
        profiles=profiles,
        best=best,
        version=version,
        algo_ops_to_schedule=algo_ops_to_schedule,
        start_dt=start_dt,
        end_date=end_date,
        base_strategy=base_strategy,
        base_params=base_params,
        dispatch_rule_cfg=dispatch_rule_cfg,
        resource_pool=resource_pool,
        objective_name=objective_name,
        deadline=deadline,
        attempts=attempts,
        improvement_trace=improvement_trace,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=readiness_gate_enabled,
        strict_mode=strict_mode,
        graph_ready_context=graph_ready_context,
        metrics_by_op_id=prepared_features.metrics_by_op_id,
        clock=clock,
        search_report_state=search_report_state,
        order=order,
        repair_limits=repair_limits,
        iterated_greedy_limits=iterated_greedy_limits,
        prepared_features=prepared_features,
        decode_session=decode_session,
    )


def _phase_skip_reason(*, algo_mode: str, graph_ready_context: Optional[Any]) -> Optional[str]:
    if graph_ready_context is None:
        return "graph_ready_unavailable"
    if str(algo_mode or "").strip().lower() != "improve":
        return "algo_mode_not_improve"
    return None


def _build_weight_profile_stages(
    *,
    profiles: List[GraphReadyWeightProfile],
    best: Optional[Dict[str, Any]],
    version: int,
    algo_ops_to_schedule: List[Any],
    start_dt: datetime,
    end_date: Optional[date],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Any,
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    clock: Callable[[], float],
    search_report_state: Optional[OptimizationSearchReportState],
    order: List[str],
    repair_limits: EliteRepairLimits,
    iterated_greedy_limits: IteratedGreedyLimits,
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    """Assemble resumable profile, repair and IG stages sharing one stable target view."""
    budget = GraphReadySearchBudget(deadline=deadline, clock=clock)
    v2_common_rank_cache = prepared_features.v2_common_rank_cache
    decision_features = prepared_features.decision_features
    evaluate = partial(
        evaluate_graph_ready_candidate,
        graph_ready_context=graph_ready_context, metrics_by_op_id=metrics_by_op_id,
        strict_mode=bool(strict_mode), algo_ops_to_schedule=algo_ops_to_schedule,
        strategy=base_strategy, params=base_params, start_dt=start_dt, end_date=end_date,
        dispatch_rule=dispatch_rule_cfg,
        resource_pool=resource_pool, objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
        readiness_gate_enabled=bool(readiness_gate_enabled), version=int(version),
        clock=clock, v2_common_rank_cache=v2_common_rank_cache,
        prepared_decision_features=decision_features,
        decode_session=decode_session,
    )
    pool = EliteRepairPool(limits=repair_limits, objective_name=objective_name, operations=algo_ops_to_schedule,
                           metrics_by_op_id=metrics_by_op_id, start_dt=start_dt, seed=version,
                           best=best, report_state=search_report_state, graph_context=graph_ready_context,
                           resource_pool=resource_pool, clock=clock, deadline=deadline, decode_session=decode_session)
    search = GraphReadyProfileSearch(evaluate=evaluate, budget=budget, profile_count=len(profiles))
    state = GraphSearchState(best)
    stages: List[SearchStage] = [ProfileStage(
        profiles=profiles, search=search, pool=pool, state=state, order=order, strict_mode=bool(strict_mode),
        base_strategy=base_strategy, dispatch_rule_cfg=dispatch_rule_cfg, attempts=attempts,
        improvement_trace=improvement_trace, search_report_state=search_report_state, clock=clock, t_begin=t_begin)]
    if _has_v2_profile(profiles) or repair_limits.enabled:
        repair = EliteRepairRun(pool, state=state, evaluate=evaluate, budget=budget, deadline=deadline, clock=clock,
                                t_begin=t_begin, attempts=attempts, improvement_trace=improvement_trace,
                                report_state=search_report_state, strict_mode=bool(strict_mode))
        stages.append(RepairStage(repair))
        greedy = IteratedGreedyRun(
            limits=iterated_greedy_limits, state=state,
            parent_profile=partial(iterated_greedy_parent_profile, pool=pool, profiles=profiles),
            pool=pool, evaluate=evaluate, operations=algo_ops_to_schedule, graph_context=graph_ready_context,
            metrics_by_op_id=metrics_by_op_id, objective_name=objective_name, start_dt=start_dt, seed=int(version),
            deadline=deadline, clock=clock, t_begin=t_begin, attempts=attempts, improvement_trace=improvement_trace,
            report_state=search_report_state, strict_mode=bool(strict_mode), decode_session=decode_session)
        stages.append(IteratedGreedyStage(greedy, startup_ready=lambda: bool(pool.elites) or not stages[0].available()))
    return GraphStageBundle(state, stages)


def _has_v2_profile(profiles: List[GraphReadyWeightProfile]) -> bool:
    return any(str(profile.formula_version or "").startswith("graph_ready_v2") for profile in list(profiles or []))


def _candidate_order(
    best: Optional[Dict[str, Any]],
    *,
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
) -> List[str]:
    order = list((best or {}).get("order") or [])
    if order:
        return order
    return list(build_order(base_strategy, base_params or {}))


__all__ = [
    "GraphStageBundle",
    "SharedGraphFeatures",
    "build_graph_search_stages",
    "prepare_shared_graph_features",
]
