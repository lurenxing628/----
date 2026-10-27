from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile, resolve_v2_profiles
from core.services.scheduler.run.optimizer.search_stage import SearchStage

from .budget import GraphReadySearchBudget
from .candidates import PreparedDecisionFeatures, evaluate_graph_ready_candidate
from .context import graph_node_metrics_by_op_id
from .iterated_greedy_contract import IteratedGreedyLimits
from .iterated_greedy_run import IteratedGreedyRun
from .predecode import GraphReadyProfileSearch
from .repair import EliteRepairPool, EliteRepairRun
from .repair_contract import EliteRepairLimits
from .stages import GraphSearchState, IteratedGreedyStage, ProfileStage, RepairStage, iterated_greedy_parent_profile
from .v2_features import enrich_graph_ready_v2_metrics
from .v2_ranks import build_v2_common_rank_cache

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession


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
    *, graph_ready_context: Dict[str, Any], scheduler: GreedyScheduler, algo_ops_to_schedule: List[OpForScheduleAlgo],
    batches: Dict[str, Any], start_dt: datetime, downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult], resource_pool: Optional[Dict[str, Any]],
    deadline: float, clock: Callable[[], float],
) -> Optional[SharedGraphFeatures]:
    """Build both existing bases and their ranks once before target stages are assembled."""
    if clock() >= deadline:
        return None
    schedulable_ids = {op.id for op in algo_ops_to_schedule}
    metrics = enrich_graph_ready_v2_metrics(
        graph_node_metrics_by_op_id(graph_ready_context, schedulable_ids=schedulable_ids),
        operations=algo_ops_to_schedule, batches=batches,
        start_dt=start_dt, calendar_service=scheduler.calendar, downtime_map=downtime_map,
        seed_results=seed_sr_list, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context,
    )
    return SharedGraphFeatures(metrics, build_v2_common_rank_cache(metrics))


def build_graph_search_stages(
    *,
    best: Optional[Dict[str, Any]],
    version: int,
    algo_ops_to_schedule: List[OpForScheduleAlgo],
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
    graph_ready_context: Dict[str, Any],
    clock: Callable[[], float],
    search_report_state: OptimizationSearchReportState,
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    """Graph stages exist only for an improve run with a prepared graph context (schedule_shared_optimizer)."""
    profiles = resolve_v2_profiles(seed=version, objective_name=objective_name)
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
        graph_ready_context=graph_ready_context,
        metrics_by_op_id=prepared_features.metrics_by_op_id,
        clock=clock,
        search_report_state=search_report_state,
        order=order,
        prepared_features=prepared_features,
        decode_session=decode_session,
    )


def _build_weight_profile_stages(
    *,
    profiles: List[GraphReadyWeightProfile],
    best: Optional[Dict[str, Any]],
    version: int,
    algo_ops_to_schedule: List[OpForScheduleAlgo],
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
    graph_ready_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    clock: Callable[[], float],
    search_report_state: OptimizationSearchReportState,
    order: List[str],
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    """Assemble resumable profile, repair and IG stages sharing one stable target view."""
    budget = GraphReadySearchBudget(deadline=deadline, clock=clock)
    evaluate = partial(
        evaluate_graph_ready_candidate,
        strategy=base_strategy, params=base_params, start_dt=start_dt, end_date=end_date,
        dispatch_rule=dispatch_rule_cfg,
        resource_pool=resource_pool, objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
        readiness_gate_enabled=bool(readiness_gate_enabled), version=version,
        clock=clock, prepared_decision_features=prepared_features.decision_features,
        decode_session=decode_session,
    )
    pool = EliteRepairPool(limits=EliteRepairLimits(), objective_name=objective_name, operations=algo_ops_to_schedule,
                           metrics_by_op_id=metrics_by_op_id, start_dt=start_dt, seed=version,
                           best=best, report_state=search_report_state, graph_context=graph_ready_context,
                           clock=clock, deadline=deadline, decode_session=decode_session)
    search = GraphReadyProfileSearch(evaluate=evaluate, budget=budget, profile_count=len(profiles))
    state = GraphSearchState(best)
    stages: List[SearchStage] = [ProfileStage(
        profiles=profiles, search=search, pool=pool, state=state, order=order, attempts=attempts,
        improvement_trace=improvement_trace, search_report_state=search_report_state, clock=clock, t_begin=t_begin)]
    repair = EliteRepairRun(pool, state=state, evaluate=evaluate, budget=budget, deadline=deadline, clock=clock,
                            t_begin=t_begin, attempts=attempts, improvement_trace=improvement_trace,
                            report_state=search_report_state)
    stages.append(RepairStage(repair))
    greedy = IteratedGreedyRun(
        limits=IteratedGreedyLimits(), state=state,
        parent_profile=partial(iterated_greedy_parent_profile, pool=pool, profiles=profiles),
        pool=pool, evaluate=evaluate, operations=algo_ops_to_schedule, graph_context=graph_ready_context,
        metrics_by_op_id=metrics_by_op_id, objective_name=objective_name, start_dt=start_dt, seed=version,
        deadline=deadline, clock=clock, t_begin=t_begin, attempts=attempts, improvement_trace=improvement_trace,
        report_state=search_report_state, decode_session=decode_session)
    stages.append(IteratedGreedyStage(greedy, startup_ready=lambda: bool(pool.elites) or not stages[0].available()))
    return GraphStageBundle(state, stages)


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
    return list(build_order(base_strategy, base_params))


__all__ = [
    "GraphStageBundle",
    "SharedGraphFeatures",
    "build_graph_search_stages",
    "prepare_shared_graph_features",
]
