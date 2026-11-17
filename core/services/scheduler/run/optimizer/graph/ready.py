from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from core.algorithm_contracts.sort_strategies import WeightedParams
from core.algorithm_contracts.types import ScheduleResult
from core.models.enums import SortStrategy
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile, resolve_v2_profiles
from core.services.scheduler.run.optimizer.search_stage import SearchStage

from .budget import GraphReadySearchBudget
from .candidates import PreparedDecisionFeatures, evaluate_graph_ready_candidate
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
    schedulable_ids: FrozenSet[int]
    decision_features: PreparedDecisionFeatures = field(init=False)

    def __post_init__(self) -> None:
        self.decision_features = PreparedDecisionFeatures(self.metrics_by_op_id, self.v2_common_rank_cache,
                                                          schedulable_ids=self.schedulable_ids)


@dataclass
class GraphStageBundle:
    """Graph generators and their stable target view, without a scheduling loop."""

    state: GraphSearchState
    stages: List[SearchStage]


def prepare_shared_graph_features(
    *, decode_session: SharedDecodeSession, graph_ready_context: Dict[str, Any], batches: Dict[str, Any],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]], seed_results: List[ScheduleResult],
) -> Optional[SharedGraphFeatures]:
    """Build both existing bases and their ranks once before target stages are assembled.

    The run's operations, start, calendar and preparation (with its resource pool) are the session's; the shared key
    admission uses the preparation's ``topology.schedulable_ids``.
    """
    native_preparation = decode_session.native_preparation
    schedulable_ids = native_preparation.graph_topology().schedulable_ids
    budget = decode_session.budget
    if budget.clock() >= budget.deadline:
        return None
    metrics = enrich_graph_ready_v2_metrics(
        graph_ready_context["node_metrics_by_op_id"],
        operations=decode_session.operations, batches=batches,
        start_dt=decode_session.start_dt, calendar_service=decode_session.scheduler.calendar,
        downtime_map=downtime_map, seed_results=seed_results, graph_ready_context=graph_ready_context,
        budget=budget, native_preparation=native_preparation,
    )
    if metrics is None or budget.clock() >= budget.deadline:
        return None
    return SharedGraphFeatures(metrics, build_v2_common_rank_cache(metrics), schedulable_ids)


def build_graph_search_stages(
    *,
    best: Optional[Dict[str, Any]],
    version: int,
    base_strategy: SortStrategy,
    base_params: Optional[WeightedParams],
    build_order: Callable[[SortStrategy, Optional[WeightedParams]], Tuple[str, ...]],
    dispatch_rule_cfg: str,
    objective_name: str,
    search_report_state: OptimizationSearchReportState,
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    """Graph stages exist only for an improve run with a prepared graph context (schedule_shared_optimizer).

    The run's inputs and time come from ``decode_session``; the rest is this target view's.
    """
    profiles = resolve_v2_profiles(seed=version, objective_name=objective_name)
    if decode_session.budget.clock() >= decode_session.budget.deadline:
        return GraphStageBundle(GraphSearchState(best), [])
    order = _candidate_order(best, build_order=build_order, base_strategy=base_strategy, base_params=base_params)
    return _build_weight_profile_stages(
        profiles=profiles,
        best=best,
        version=version,
        base_strategy=base_strategy,
        base_params=base_params,
        dispatch_rule_cfg=dispatch_rule_cfg,
        objective_name=objective_name,
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
    base_strategy: SortStrategy,
    base_params: Optional[WeightedParams],
    dispatch_rule_cfg: str,
    objective_name: str,
    search_report_state: OptimizationSearchReportState,
    order: Sequence[str],
    prepared_features: SharedGraphFeatures,
    decode_session: SharedDecodeSession,
) -> GraphStageBundle:
    """Assemble resumable profile, repair and IG stages sharing one stable target view."""
    budget = GraphReadySearchBudget(decode_session.budget)
    evaluate = partial(
        evaluate_graph_ready_candidate,
        strategy=base_strategy, params=base_params, dispatch_rule=dispatch_rule_cfg,
        objective_name=objective_name, version=version,
        prepared_decision_features=prepared_features.decision_features,
        decode_session=decode_session,
    )
    pool = EliteRepairPool(limits=EliteRepairLimits(), objective_name=objective_name,
                           operations=decode_session.operations, seed=version,
                           best=best, report_state=search_report_state, decode_session=decode_session,
                           decision_features=prepared_features.decision_features)
    search = GraphReadyProfileSearch(evaluate=evaluate, budget=budget)
    state = GraphSearchState(best)
    stages: List[SearchStage] = [ProfileStage(
        profiles=profiles, search=search, pool=pool, state=state, order=order,
        search_report_state=search_report_state)]
    repair = EliteRepairRun(pool, state=state, evaluate=evaluate, budget=budget, report_state=search_report_state)
    stages.append(RepairStage(repair))
    greedy = IteratedGreedyRun(
        limits=IteratedGreedyLimits(), state=state,
        parent_profile=partial(iterated_greedy_parent_profile, pool=pool, profiles=profiles),
        pool=pool, evaluate=evaluate,
        metrics_by_op_id=prepared_features.metrics_by_op_id, objective_name=objective_name, seed=version,
        report_state=search_report_state, decode_session=decode_session)
    stages.append(IteratedGreedyStage(greedy, startup_ready=lambda: bool(pool.elites) or not stages[0].available()))
    return GraphStageBundle(state, stages)


def _candidate_order(
    best: Optional[Dict[str, Any]],
    *,
    build_order: Callable[[SortStrategy, Optional[WeightedParams]], Tuple[str, ...]],
    base_strategy: SortStrategy,
    base_params: Optional[WeightedParams],
) -> Sequence[str]:
    return (best or {}).get("order") or build_order(base_strategy, base_params)


__all__ = [
    "GraphStageBundle",
    "SharedGraphFeatures",
    "build_graph_search_stages",
    "prepare_shared_graph_features",
]
