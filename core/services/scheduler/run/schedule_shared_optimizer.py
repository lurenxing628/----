"""One internal optimizer session over an owned archive and resumable generators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from core.algorithm_contracts.ordering import build_batch_sort_inputs
from core.algorithm_contracts.sort_strategies import SortStrategy, StrategyFactory
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithms.evaluation import prepare_evaluation_context
from core.errors import ValidationError
from core.models.batch import Batch
from core.models.objective import target_objectives_for
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

from .optimizer.candidate_profile import build_candidate_profile
from .optimizer.config import is_ortools_enabled, resolve_optimizer_config
from .optimizer.graph.ready import (
    GraphReadyDeadlineExhausted,
    build_graph_search_stages,
    prepare_shared_graph_features,
)
from .optimizer.graph.stages import ProfileStage
from .optimizer.grasp_ig_candidates import GraspIGStage
from .optimizer.local_search import LocalSearchStage
from .optimizer.multi_start import MultiStartStage
from .optimizer.neighborhood_moves import BUSINESS_NEIGHBORHOODS
from .optimizer.runtime import OptimizerRuntime, resolve_runtime
from .optimizer.search_budget import SearchBudget, SearchBudgetExhausted
from .optimizer.search_report import OptimizationSearchReportState
from .optimizer.search_stage import SearchStage
from .optimizer.search_state import OptimizerSearchState
from .optimizer.shared_archive import SharedScheduleArchive
from .optimizer.shared_budget import SharedSearchBudget
from .optimizer.shared_decode import SharedDecodeSession
from .optimizer.shared_process import build_shared_process
from .schedule_seed_contracts import coerce_seed_results
from .schedule_shared_search import GoalView, SharedSearch


@dataclass
class SharedOptimizationResult:
    archive: SharedScheduleArchive
    target_objectives: Tuple[str, ...]
    process_facts: Dict[str, Any]


class _WarmStartStage(SearchStage):
    name = "ortools_warmstart"

    def __init__(self, *, run: Callable[[], None], clock: Callable[[], float], deadline: float) -> None:
        self.run, self.clock, self.deadline = run, clock, deadline
        self.done = False

    def available(self) -> bool:
        return not self.done and self.deadline - self.clock() >= 1.0

    def run_task(self) -> None:
        self.done = True
        self.run()

    def finish(self) -> None:
        self.done = True

    def unavailable_reason(self) -> Optional[str]:
        return "finished" if self.done else "remaining_time_less_than_one_second"


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
    *, calendar_service: Any, cfg: ScheduleConfigSnapshot, algo_ops_to_schedule: List[OpForScheduleAlgo],
    batches: Dict[str, Batch], start_dt: datetime, end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]], seed_results: List[Dict[str, Any]],
    resource_pool: Optional[Dict[str, Any]], version: int,
    readiness_gate_enabled: bool = False,
    graph_ready_context: Optional[Any] = None, graph_dispatch_mode_override: Optional[str] = None,
    graph_prepare: Optional[Callable[[], Any]] = None, search_budget: SearchBudget,
    _runtime: Optional[OptimizerRuntime] = None,
) -> SharedOptimizationResult:
    """Construct once, then rotate one action at a time over all target generators."""
    runtime = resolve_runtime(_runtime, search_budget)
    started_at = runtime.clock()
    algo_stats: Dict[str, Any] = {"fallback_counts": {}}
    if graph_dispatch_mode_override not in (None, "sgs"):
        raise ValidationError("图派工模式覆盖只允许使用 sgs。", field="graph_dispatch_mode_override")
    seeds = coerce_seed_results(seed_results, optimizer_algo_stats=algo_stats)
    scheduler = runtime.scheduler_factory(calendar_service=calendar_service, config_service=cfg)
    config = resolve_optimizer_config(cfg)
    # The only caller (schedule_candidate_runner) owns the run's budget.
    deadline = search_budget.deadline
    configured_seconds = search_budget.assigned_seconds
    if runtime.clock() >= deadline:
        raise SearchBudgetExhausted("candidate_time_budget_reached")

    graph_preparation_calls = 0
    if graph_prepare is not None:
        preparation = graph_prepare()
        graph_preparation_calls = 1
        graph_ready_context = preparation.graph_ready_context
        graph_dispatch_mode_override = preparation.graph_dispatch_mode_override
    piece = bool(graph_ready_context is not None and graph_ready_context.get("piece_scope"))
    if any(op.piece_id is not None for op in algo_ops_to_schedule) and not piece:
        raise ValidationError("分件排产需要真实工艺依赖图。", field="graph_ready_context")
    ordinary_context = dict(cast(Dict[str, Any], graph_ready_context), score_enabled=False) if piece else None
    forced_sgs = piece or graph_dispatch_mode_override == "sgs"
    dispatch_mode = "sgs" if forced_sgs else config.dispatch_mode
    dispatch_modes = ["sgs"] if forced_sgs else config.dispatch_modes()
    evaluation_context = prepare_evaluation_context(
        batches=batches, expected_operations=algo_ops_to_schedule, seed_results=seeds,
    )
    targets = target_objectives_for(config.objective_name)
    archive = SharedScheduleArchive(config.objective_name, targets, evaluation_context.batch_by_op_id,
                                    set(batches) | set(evaluation_context.expected_by_batch))
    shared_budget = SharedSearchBudget(clock=runtime.clock, started_at=started_at, deadline=deadline,
                                      target_objectives=targets, configured_seconds=configured_seconds)
    session = SharedSearch(archive=archive, clock=runtime.clock, started_at=started_at, budget=shared_budget)
    session.decode_session = SharedDecodeSession(
        archive=archive, budget=shared_budget, scheduler=scheduler, operations=algo_ops_to_schedule,
        batches=batches, seed_results=seeds, downtime_map=downtime_map, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context, clock=runtime.clock, started_at=started_at, deadline=deadline,
        event_sink=session.record_event, evaluation_context=evaluation_context)
    native_preparation = session.decode_session.native_preparation

    def build_order(strategy: SortStrategy, params: Dict[str, Any]) -> List[str]:
        sortable = build_batch_sort_inputs(native_preparation.batches, strategy=strategy,
                                           readiness_gate_enabled=bool(readiness_gate_enabled))
        sorter = StrategyFactory.create(strategy, **params)
        return [item.batch_id for item in sorter.sort(sortable, base_date=start_dt.date())]

    profile = build_candidate_profile(
        algo_mode=config.algo_mode, time_budget_seconds=config.time_budget_seconds,
        ortools_enabled=is_ortools_enabled(cfg), graph_sgs_required=piece,
    )
    for target in targets:
        report = OptimizationSearchReportState(
            objective_name=target, started_at=started_at,
            candidate_clock=runtime.clock,
            candidate_observer=lambda *, _target=target, **kw: session.observe(_target, **kw),
            candidate_acceptance_observer=lambda *, _target=target, **kw: session.accept(_target, **kw),
            reference_capture_observer=lambda *, _target=target, **kw: session.capture(_target, **kw),
        )
        session.views[target] = GoalView(target, OptimizerSearchState(), report)
    primary = session.views[targets[0]]
    decode_common: Dict[str, Any] = dict(
        start_dt=start_dt, end_date=end_date, resource_pool=resource_pool, deadline=deadline,
        optimizer_algo_stats=algo_stats, t_begin=started_at, readiness_gate_enabled=bool(readiness_gate_enabled),
        clock=runtime.clock, decode_session=session.decode_session,
    )
    common: Dict[str, Any] = dict(
        decode_common, scheduler=scheduler, algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches, downtime_map=downtime_map, seed_sr_list=seeds,
    )
    construction = MultiStartStage(**decode_common, cfg=cfg, keys=config.strategy_keys(), dispatch_modes=dispatch_modes,
        dispatch_rule_cfg=config.dispatch_rule, valid_dispatch_rules=list(config.valid_dispatch_rules),
        objective_name=targets[0], build_order=build_order, graph_ready_context=ordinary_context,
        state=primary.state, search_report_state=primary.report)
    primary.stages.append(construction)
    if not construction.available():
        raise SearchBudgetExhausted("candidate_time_budget_reached")
    preparation_finished_at = runtime.clock()
    shared_budget.charge_preparation(targets[0], "preparation", preparation_finished_at - started_at)
    session.run_action(primary, construction, initial=True)
    initial_construction_count = construction.index
    prepared_features = None
    feature_preparation_calls = 0
    graph_enabled = (
        cfg.graph_analysis_mode == "on"
        and graph_ready_context is not None
        and (piece or graph_ready_context.get("score_enabled") is not False)
    )
    if config.algo_mode == "improve" and graph_enabled and runtime.clock() < deadline:
        feature_preparation_calls = 1
        feature_started_at = runtime.clock()
        try:
            prepared_features = prepare_shared_graph_features(
                **{key: common[key] for key in ("scheduler", "algo_ops_to_schedule", "batches", "start_dt",
                                               "downtime_map", "seed_sr_list", "resource_pool", "deadline", "clock")},
                graph_ready_context=cast(Dict[str, Any], graph_ready_context))
        except GraphReadyDeadlineExhausted:
            pass
        finally:
            shared_budget.charge_preparation(targets[0], "graph_features", runtime.clock() - feature_started_at)

    def prepare_view(view: GoalView) -> None:
        if view.prepared:
            return
        view_started_at = runtime.clock()
        session.search_objective, session.phase = view.objective, "prepare_view"
        session.sync(view)
        view.prepared = True
        if view.objective == targets[0] and profile.ortools_warmstart_enabled:
            def warmstart() -> None:
                view.state.best = runtime.run_ortools_warmstart(
                    **decode_common, algo_ops_to_schedule=algo_ops_to_schedule, batches=batches,
                    algo_mode=config.algo_mode, cfg=cfg, strategy_enum=config.strategy_enum, objective_name=view.objective,
                    dispatch_mode_cfg=dispatch_mode, dispatch_rule_cfg=config.dispatch_rule,
                    attempts=view.state.attempts, improvement_trace=view.state.improvement_trace, best=view.state.best,
                    graph_ready_context=ordinary_context, search_report_state=view.report)
            view.stages.append(_WarmStartStage(run=warmstart, clock=runtime.clock, deadline=deadline))
        if not piece:
            view.local_stage = LocalSearchStage(
                **decode_common, batches=batches, best=view.state.best, version=version,
                dispatch_mode_cfg=dispatch_mode, dispatch_rule_cfg=config.dispatch_rule, objective_name=view.objective,
                attempts=view.state.attempts, improvement_trace=view.state.improvement_trace,
                rng_factory=runtime.rng_factory, search_report_state=view.report,
                neighborhoods=_business_neighborhoods(view.objective),
                valid_dispatch_rules=list(config.valid_dispatch_rules), acceptance=profile.acceptance)
            view.stages.append(view.local_stage)
            view.stages.append(GraspIGStage(
                **decode_common, version=version,
                candidate_construction=profile.candidate_construction, base_strategy=config.strategy_enum,
                base_params=config.strategy_params, build_order=build_order, dispatch_rule_cfg=config.dispatch_rule,
                objective_name=view.objective, rng_factory=runtime.rng_factory,
                batch_order_enabled="batch_order" in dispatch_modes, search_report_state=view.report, state=view.state))
        if prepared_features is not None and runtime.clock() < deadline:
            view.graph_bundle = build_graph_search_stages(
                **decode_common, algo_ops_to_schedule=algo_ops_to_schedule, best=view.state.best,
                version=version, base_strategy=config.strategy_enum, base_params=config.strategy_params,
                build_order=build_order, dispatch_rule_cfg=config.dispatch_rule, objective_name=view.objective,
                attempts=view.state.attempts, improvement_trace=view.state.improvement_trace,
                graph_ready_context=cast(Dict[str, Any], graph_ready_context),
                search_report_state=view.report, prepared_features=prepared_features)
            view.stages.extend(view.graph_bundle.stages)
        shared_budget.charge_preparation(view.objective, "prepare_view", runtime.clock() - view_started_at)

    stop_reason = "greedy_single_construction" if config.algo_mode != "improve" else "search_exhausted"
    try:
        while config.algo_mode == "improve":
            reason = shared_budget.should_stop()
            if reason is not None:
                stop_reason = reason
                break
            candidates = targets if archive.best_by_objective else targets[:1]
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
        shutdown_started_at = runtime.clock()
        for view in session.views.values():
            for stage in view.stages:
                stage.finish()
        shared_budget.charge_preparation(session.search_objective, "search_finalize", runtime.clock() - shutdown_started_at)
    session.sync(primary)
    best = primary.candidate
    if best is None:
        raise SearchBudgetExhausted("candidate_time_budget_reached")
    finished_at = runtime.clock()
    runtime_ms = max(int((finished_at - started_at) * 1000), 0)
    budget_stats = shared_budget.summary(finished_at=finished_at)
    decode_stats = session.decode_session.stats()
    facts = {
        "events": session.events, "actions": session.actions, "bridges": session.bridges,
        "initial_entry_id": session.initial_entry_id,
        "initial_construction_count": initial_construction_count,
        "first_complete_elapsed_ms": session.first_complete_elapsed_ms,
        "graph_preparation_calls": graph_preparation_calls, "feature_preparation_calls": feature_preparation_calls,
        "runtime_ms": runtime_ms, "stop_reason": stop_reason,
        "selected_entries_by_objective": {target: session.selected_entry(target) for target in targets},
        "evidence_event_ids_by_entry": dict(session.evidence_event_ids),
    }
    facts["unified_process"] = build_shared_process(session, runtime_ms=runtime_ms, stop_reason=stop_reason,
        decode_stats=decode_stats, budget_stats=budget_stats)
    return SharedOptimizationResult(archive, targets, facts)


__all__ = ["SharedOptimizationResult", "optimize_shared_schedule"]
