"""One internal optimizer session over an owned archive and resumable generators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, cast

from core.algorithm_contracts.resource_pool import ResourcePool
from core.algorithm_contracts.sort_strategies import WeightedParams
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.errors import ValidationError
from core.models.batch import Batch
from core.models.enums import SortStrategy

from .optimizer.candidate_profile import derive_grasp_ig_limits
from .optimizer.config import resolve_optimizer_config
from .optimizer.graph.ready import (
    SharedGraphFeatures,
    build_graph_search_stages,
    prepare_shared_graph_features,
)
from .optimizer.graph.stages import ProfileStage
from .optimizer.grasp_ig_candidates import GraspIGStage
from .optimizer.local_search import LocalSearchStage
from .optimizer.multi_start import MultiStartStage
from .optimizer.neighborhood_moves import BUSINESS_NEIGHBORHOODS
from .optimizer.search_budget import SearchBudget, SearchBudgetExhausted
from .optimizer.search_stage import SearchStage
from .optimizer.shared_archive import SharedScheduleArchive
from .optimizer.shared_budget import SharedSearchBudget
from .optimizer.shared_process import build_shared_process
from .schedule_seed_contracts import coerce_seed_results
from .schedule_shared_search import GoalView, open_shared_search

if TYPE_CHECKING:
    from core.algorithms.greedy.scheduler import GreedyScheduler


@dataclass
class SharedOptimizationResult:
    archive: SharedScheduleArchive
    target_objectives: Tuple[str, ...]
    process_facts: Dict[str, Any]


def _business_neighborhoods(objective: str) -> Tuple[str, ...]:
    first = {
        "min_overdue": ("tardy_window", "time_window"),
        "min_tardiness": ("tardy_window", "time_window"),
        "min_weighted_tardiness": ("tardy_window", "resource_alternative"),
        "min_changeover": ("changeover_block", "resource_alternative"),
    }[objective]
    return first + tuple(neighborhood for neighborhood in BUSINESS_NEIGHBORHOODS if neighborhood not in first)


def _next_stage(view: GoalView, *, first_opportunity: bool = False) -> Optional[SearchStage]:
    if first_opportunity and not view.first_opportunity_selected:
        view.first_opportunity_selected = True
        for stage_type in (ProfileStage, LocalSearchStage):
            for stage in view.stages:
                if not isinstance(stage, stage_type):
                    continue
                if stage.available():
                    view.stage_index = (view.stages.index(stage) + 1) % len(view.stages)
                    return stage
    available = []
    for offset in range(len(view.stages)):
        index = (view.stage_index + offset) % len(view.stages)
        stage = view.stages[index]
        if stage.available():
            available.append((view.stage_charged_seconds.get(id(stage), 0.0), offset, index, stage))
    if not available:
        return None
    _charged, _offset, index, stage = min(available, key=lambda item: item[:2])
    view.stage_index = (index + 1) % len(view.stages)
    return stage


def _mark_view_unavailable(shared_budget: SharedSearchBudget, objective: str, stages: Sequence[SearchStage]) -> None:
    reasons = [stage.unavailable_reason() for stage in stages]
    waiting = any(reason in ("awaiting_parent", "waiting_for_parent", "waiting_for_repair_parent",
                             "no_elite", "no_incumbent") for reason in reasons)
    shared_budget.mark_unavailable(
        objective, "waiting_for_parent" if waiting else "stages_exhausted",
        not_applicable=not waiting and not any(reason in ("time_budget", "estimated_decode_cost") for reason in reasons),
    )


def optimize_shared_schedule(
    *, scheduler: GreedyScheduler, algo_ops_to_schedule: List[OpForScheduleAlgo],
    batches: Dict[str, Batch], required_hours_by_op_id: Mapping[int, float], start_dt: datetime, end_date: date,
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]], seed_results: List[Dict[str, Any]],
    resource_pool: ResourcePool, version: int,
    readiness_gate_enabled: bool,
    graph_prepare: Callable[[], Any], search_budget: SearchBudget,
) -> SharedOptimizationResult:
    """Construct once, then rotate one action at a time over all target generators.

    ``scheduler`` is the run's decoder (its ``config`` is the run configuration). The run's clock arrives with
    the request budget; once the search is open, every time reading is the shared budget's.
    """
    cfg = scheduler.config
    started_at = search_budget.clock()
    seeds = coerce_seed_results(seed_results)
    config = resolve_optimizer_config(cfg)
    # The only caller (schedule_candidate_runner) owns the run's budget.
    deadline = search_budget.deadline
    if search_budget.clock() >= deadline:
        raise SearchBudgetExhausted("candidate_time_budget_reached")

    preparation = graph_prepare()
    graph_ready_context: Optional[Any] = preparation.graph_ready_context
    graph_dispatch_mode_override: Optional[str] = preparation.graph_dispatch_mode_override
    piece = bool(graph_ready_context is not None and graph_ready_context.get("piece_scope"))
    if any(op.piece_id is not None for op in algo_ops_to_schedule) and not piece:
        raise ValidationError("分件排产需要真实工艺依赖图。", field="graph_ready_context")
    ordinary_context = dict(cast(Dict[str, Any], graph_ready_context), score_enabled=False) if piece else None
    forced_sgs = piece or graph_dispatch_mode_override == "sgs"
    dispatch_modes = ["sgs"] if forced_sgs else config.dispatch_modes()
    session = open_shared_search(
        objective_name=config.objective_name, scheduler=scheduler, operations=algo_ops_to_schedule,
        batches=batches, required_hours_by_op_id=required_hours_by_op_id, seed_results=seeds,
        downtime_map=downtime_map, resource_pool=resource_pool, graph_ready_context=graph_ready_context,
        start_dt=start_dt, end_date=end_date, readiness_gate_enabled=readiness_gate_enabled,
        clock=search_budget.clock, started_at=started_at, deadline=deadline,
        configured_seconds=search_budget.assigned_seconds)
    archive, shared_budget, decode_session = session.archive, session.budget, session.decode_session
    clock = shared_budget.clock
    targets = archive.target_objectives
    native_preparation = decode_session.native_preparation

    def build_order(strategy: SortStrategy, weights: Optional[WeightedParams]) -> Tuple[str, ...]:
        return native_preparation.batch_order(start_dt=start_dt, strategy=strategy, weights=weights)

    for target in targets:
        session.open_view(target)
    primary = session.views[targets[0]]
    construction = MultiStartStage(cfg=cfg, keys=config.strategy_keys(), dispatch_modes=dispatch_modes,
        dispatch_rule_cfg=config.dispatch_rule, valid_dispatch_rules=list(config.valid_dispatch_rules),
        objective_name=targets[0], build_order=build_order, graph_ready_context=ordinary_context,
        state=primary.state, search_report_state=primary.report, decode_session=decode_session)
    primary.stages.append(construction)
    if not construction.available():
        raise SearchBudgetExhausted("candidate_time_budget_reached")
    preparation_finished_at = clock()
    shared_budget.charge_preparation(targets[0], "preparation", preparation_finished_at - started_at)
    session.run_action(primary, construction, initial=True)
    initial_construction_count = construction.index
    prepared_features: Optional[SharedGraphFeatures] = None
    feature_preparation_calls = 0
    graph_features_attempted = False
    graph_enabled = (
        cfg.graph_analysis_mode == "on"
        and graph_ready_context is not None
        and graph_ready_context.get("score_enabled") is not False
    )

    def prepare_graph_features() -> Optional[SharedGraphFeatures]:
        nonlocal prepared_features, feature_preparation_calls, graph_features_attempted
        if graph_features_attempted:
            return prepared_features
        if (
            config.algo_mode != "improve"
            or not graph_enabled
            or shared_budget.should_stop() is not None
            or not shared_budget.can_afford_decode("sgs_full")
        ):
            return None
        graph_features_attempted = True
        feature_preparation_calls += 1
        feature_started_at = clock()
        try:
            prepared_features = prepare_shared_graph_features(
                decode_session=decode_session, graph_ready_context=cast(Dict[str, Any], graph_ready_context),
                batches=batches, downtime_map=downtime_map, seed_results=seeds)
        finally:
            shared_budget.charge_preparation(targets[0], "graph_features", clock() - feature_started_at)
        return prepared_features

    def prepare_view(view: GoalView) -> None:
        if view.prepared:
            return
        features = prepare_graph_features()
        view_started_at = clock()
        session.search_objective, session.phase = view.objective, "prepare_view"
        session.sync(view)
        view.prepared = True
        if not piece:
            view.local_stage = LocalSearchStage(
                best=view.state.best, version=version, objective_name=view.objective,
                search_report_state=view.report, neighborhoods=_business_neighborhoods(view.objective),
                valid_dispatch_rules=list(config.valid_dispatch_rules), decode_session=decode_session)
            view.stages.append(view.local_stage)
            view.stages.append(GraspIGStage(
                version=version, candidate_construction=derive_grasp_ig_limits(config.time_budget_seconds),
                base_strategy=config.strategy_enum,
                base_params=config.strategy_params, build_order=build_order, dispatch_rule_cfg=config.dispatch_rule,
                objective_name=view.objective, batch_order_enabled="batch_order" in dispatch_modes,
                search_report_state=view.report, state=view.state, decode_session=decode_session))
        if (
            features is not None
            and shared_budget.should_stop() is None
            and shared_budget.can_afford_decode("sgs_full")
        ):
            view.graph_bundle = build_graph_search_stages(
                best=view.state.best, version=version, base_strategy=config.strategy_enum,
                base_params=config.strategy_params, build_order=build_order, dispatch_rule_cfg=config.dispatch_rule,
                objective_name=view.objective, search_report_state=view.report, prepared_features=features,
                decode_session=decode_session)
            view.stages.extend(view.graph_bundle.stages)
        shared_budget.charge_preparation(view.objective, "prepare_view", clock() - view_started_at)

    stop_reason = "greedy_single_construction" if config.algo_mode != "improve" else "search_exhausted"
    try:
        while config.algo_mode == "improve":
            reason = shared_budget.should_stop()
            if reason is not None:
                stop_reason = reason
                break
            candidates = targets if archive.has_complete_best() else targets[:1]
            available = []
            for objective in candidates:
                view = session.views[objective]
                if not view.prepared or any(stage.available() for stage in view.stages):
                    available.append(objective)
                else:
                    _mark_view_unavailable(shared_budget, objective, view.stages)
            objective = shared_budget.select_goal(available)
            if objective is None:
                stop_reason = shared_budget.should_stop() or "search_exhausted"
                break
            view = session.views[objective]
            prepare_view(view)
            stage = _next_stage(view, first_opportunity=not shared_budget.has_minimum_opportunity(objective))
            if stage is None:
                _mark_view_unavailable(shared_budget, objective, view.stages)
                continue
            session.run_action(view, stage)
    finally:
        shutdown_started_at = clock()
        for view in session.views.values():
            for stage in view.stages:
                stage.finish()
        shared_budget.charge_preparation(session.search_objective, "search_finalize", clock() - shutdown_started_at)
    session.sync(primary)
    best = primary.candidate
    if best is None:
        raise SearchBudgetExhausted("candidate_time_budget_reached")
    finished_at = clock()
    runtime_ms = max(int((finished_at - started_at) * 1000), 0)
    budget_stats = shared_budget.summary(finished_at=finished_at)
    decode_stats = decode_session.stats()
    facts = {
        "events": session.events, "actions": session.actions, "bridges": session.bridges,
        "initial_entry_id": session.initial_entry_id,
        "initial_construction_count": initial_construction_count,
        "first_complete_elapsed_ms": session.first_complete_elapsed_ms,
        "feature_preparation_calls": feature_preparation_calls,
        "runtime_ms": runtime_ms, "stop_reason": stop_reason,
        "selected_entries_by_objective": {target: archive.selected_entry(target) for target in targets},
        "evidence_event_ids_by_entry": dict(session.evidence_event_ids),
    }
    facts["unified_process"] = build_shared_process(session, runtime_ms=runtime_ms, stop_reason=stop_reason,
        decode_stats=decode_stats, budget_stats=budget_stats)
    return SharedOptimizationResult(archive, targets, facts)


__all__ = ["SharedOptimizationResult", "optimize_shared_schedule"]
