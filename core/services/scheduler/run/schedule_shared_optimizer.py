"""One internal optimizer session over an owned archive and resumable generators."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from core.algorithm_contracts.ordering import build_batch_sort_inputs
from core.algorithms import SortStrategy, StrategyFactory
from core.algorithms.evaluation import prepare_evaluation_context
from core.errors import ValidationError
from core.models.objective import target_objectives_for

from .optimizer.candidate_profile import build_candidate_profile
from .optimizer.config import ensure_optimizer_config_snapshot, is_ortools_enabled, resolve_optimizer_config
from .optimizer.graph.ready import (
    GraphStageBundle,
    _GraphReadyDeadlineExhausted,
    build_graph_search_stages,
    prepare_shared_graph_features,
)
from .optimizer.graph.stages import IteratedGreedyStage, ProfileStage, RepairStage
from .optimizer.graph_ready_profiles import graph_ready_v2_profile_summary
from .optimizer.grasp_ig_candidates import GraspIGStage
from .optimizer.local_search import LocalSearchStage
from .optimizer.multi_start import MultiStartStage
from .optimizer.neighborhood_moves import BUSINESS_NEIGHBORHOODS
from .optimizer.outcome import OptimizationOutcome, _record_decoder_invocations
from .optimizer.runtime import OptimizerRuntime, _resolve_runtime
from .optimizer.search_budget import SearchBudget, SearchBudgetExhausted
from .optimizer.search_report import OptimizationSearchReportState
from .optimizer.search_stage import SearchStage
from .optimizer.search_state import OptimizerSearchState
from .optimizer.shared_archive import ArchiveObservation, SharedScheduleArchive
from .optimizer.shared_budget import SharedSearchBudget, SharedSearchSkip
from .optimizer.shared_decode import SharedDecodeSession
from .optimizer.shared_process import build_shared_process
from .schedule_seed_contracts import coerce_seed_results


@dataclass
class SharedOptimizationResult:
    archive: SharedScheduleArchive
    primary_outcome: OptimizationOutcome
    target_objectives: Tuple[str, ...]
    process_facts: Dict[str, Any]


@dataclass
class _GoalView:
    objective: str
    state: OptimizerSearchState
    report: OptimizationSearchReportState
    stages: List[SearchStage] = field(default_factory=list)
    graph_bundle: Optional[GraphStageBundle] = None
    local_stage: Optional[LocalSearchStage] = None
    entry_id: Optional[int] = None
    evidence_revision: int = -1
    candidate: Optional[Dict[str, Any]] = None
    prepared: bool = False
    stage_index: int = 0
    first_opportunity_selected: bool = False
    stage_charged_seconds: Dict[int, float] = field(default_factory=dict)


class _WarmStartStage(SearchStage):
    name = "ortools_warmstart"

    def __init__(self, *, run: Callable[[], None], clock: Callable[[], float], deadline: float) -> None:
        self.run, self.clock, self.deadline = run, clock, deadline
        self.done = False

    def available(self) -> bool:
        return not self.done and self.deadline - self.clock() >= 1.0

    def run_task(self) -> int:
        self.done = True
        self.run()
        return 0

    def finish(self) -> None:
        self.done = True

    def unavailable_reason(self) -> Optional[str]:
        return "finished" if self.done else "remaining_time_less_than_one_second"


class _SharedSearch:
    """Own archive observations and refresh stable target views only at action boundaries."""

    def __init__(self, *, archive: SharedScheduleArchive, clock: Callable[[], float], started_at: float,
                 budget: Optional[SharedSearchBudget] = None) -> None:
        self.archive, self.clock, self.started_at = archive, clock, started_at
        self.budget = budget
        self.decode_session: Optional[SharedDecodeSession] = None
        self.views: Dict[str, _GoalView] = {}
        self.revisions: Dict[int, int] = {}
        self.phase = "preparation"
        self.search_objective = archive.primary_objective
        self.events: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []
        self.bridges: List[Dict[str, Any]] = []
        self.trajectories: Dict[str, List[Dict[str, Any]]] = {objective: [] for objective in archive.target_objectives}
        self.initial_entry_id: Optional[int] = None
        self.first_complete_elapsed_ms: Optional[int] = None
        self.evidence_event_ids: Dict[int, int] = {}
        self.trajectory_entries: Dict[str, Tuple[int, int]] = {}

    def record_event(self, fact: Dict[str, Any]) -> int:
        event = {
            "search_objective": self.search_objective, "phase": self.phase,
            "verified": False, "entry_id": None, "improved_objectives": [],
            "parent_entry_id": self.archive.current_by_objective[self.search_objective], **fact,
        }
        event["event_id"] = len(self.events) + 1
        event.setdefault("elapsed_ms", max(int((self.clock() - self.started_at) * 1000), 0))
        self.events.append(event)
        return event["event_id"]

    def observe(self, objective: str, *, candidate: Dict[str, Any], origin: str,
                verified: bool, elapsed_ms: int) -> None:
        receipt = candidate.get("decode_receipt")
        source = {
            "search_objective": objective, "phase": self.phase, "origin": origin,
            "dispatch_mode": candidate.get("dispatch_mode"), "dispatch_rule": candidate.get("dispatch_rule"),
            "strategy": str(getattr(candidate.get("strategy"), "value", candidate.get("strategy"))),
            "repair_decision": candidate.get("repair_decision"),
        }
        if receipt is not None:
            source.update(request_id=receipt["request_id"], source_event_ref=receipt.get("source_event_ref"),
                          execution_kind=receipt["execution_kind"])
        observed: Optional[ArchiveObservation] = candidate.pop("_archive_observation", None)
        if observed is None:
            entry_id = candidate.get("_shared_entry_id")
            if entry_id is None:
                raise ValueError("A decoded candidate must receive its archive identity before reporting.")
            observed = ArchiveObservation(entry_id=entry_id, reused=True,
                                          reason=None if verified else "validation_unknown")
        entry_id = observed.entry_id
        retained = entry_id in self.archive
        if retained and verified:
            self.archive.finish_observation(observed, candidate, origin=source)
        strict_improvements = (list(observed.improved_objectives)
                               if retained and entry_id is not None
                               and self.archive.entry(entry_id).score_scope.is_complete else [])
        if self.decode_session is not None and receipt is not None and retained:
            self.decode_session.bind_observation(receipt, observed.entry_id, verified, candidate=candidate)
        event_source = {key: value for key, value in source.items() if key != "repair_decision"}
        event: Dict[str, Any] = dict(event_source, event_type="archive_observation", elapsed_ms=elapsed_ms,
                                    verified=verified, entry_id=observed.entry_id, reason=observed.reason,
                                    content_reused=observed.reused, restored=observed.restored,
                                    evidence_updated=observed.evidence_updated,
                                    initialized_objectives=list(observed.initialized_objectives),
                                    improved_objectives=strict_improvements)
        if receipt is not None:
            event["decode_receipt"] = dict(receipt)
            event["request_id"] = receipt["request_id"]
        event_id = self.record_event(event)
        event = self.events[-1]
        if retained and entry_id is not None and verified:
            candidate["_shared_entry_id"] = entry_id
            entry = self.archive.entry(entry_id)
            event["evaluations"] = {target: {"field_order": list(evaluation.field_order),
                                              "score": list(evaluation.score)}
                                    for target, evaluation in entry.evaluations.items()}
            event["score_scope"] = entry.score_scope
            if not entry.score_scope.is_complete:
                event["partial_group_improved_objectives"] = list(observed.improved_objectives)
            if self.initial_entry_id is None:
                self.initial_entry_id = entry_id
            if entry_id not in self.evidence_event_ids or observed.evidence_updated:
                self.evidence_event_ids[entry_id] = event_id
            if observed.evidence_updated:
                self.revisions[entry_id] = self.revisions.get(entry_id, 0) + 1
            candidate["_shared_evidence_revision"] = self.revisions.get(entry_id, 0)
            if entry.score_scope.is_complete and self.first_complete_elapsed_ms is None:
                self.first_complete_elapsed_ms = elapsed_ms
            for target in self.archive.target_objectives:
                selected_id = self.selected_entry(target)
                if selected_id is None:
                    continue
                selected_revision = self.revisions.get(selected_id, 0)
                if self.trajectory_entries.get(target) == (selected_id, selected_revision):
                    continue
                self.trajectory_entries[target] = (selected_id, selected_revision)
                selected = self.archive.entry(selected_id)
                evaluation = selected.evaluations[target]
                self.trajectories[target].append({
                    "elapsed_ms": elapsed_ms, "entry_id": selected_id,
                    "source_event_id": self.evidence_event_ids.get(selected_id),
                    "search_objective": selected.evidence_origin.get("search_objective"),
                    "origin": selected.evidence_origin.get("origin"), "score": list(evaluation.score),
                    "field_order": list(evaluation.field_order), "score_scope": selected.score_scope,
                })
            if entry.score_scope.is_complete:
                for target in self.archive.target_objectives:
                    if not self.archive.starting_entries_by_objective[target]:
                        self.archive.set_starting_entries(target, (entry_id,))
                    if self.archive.current_by_objective[target] is None:
                        self.archive.accept_exploration(target, entry_id)

    def accept(self, objective: str, *, candidate: Dict[str, Any]) -> None:
        entry_id = candidate.get("_shared_entry_id")
        if entry_id is not None and entry_id in self.archive:
            self.archive.accept_exploration(objective, entry_id)

    def capture(self, objective: str, *, before: Dict[str, Any], after: Optional[Dict[str, Any]],
                started_at: float, finished_at: float, decoder_executed: bool, reference_kind: str) -> None:
        before_id = before.get("_shared_entry_id")
        after_id = after.get("_shared_entry_id") if after is not None else None
        bridge = {
            "search_objective": objective, "phase": self.phase, "before_entry_id": before_id,
            "after_entry_id": after_id, "elapsed_ms": max((finished_at - started_at) * 1000.0, 0.0),
            "started_elapsed_ms": max(int((started_at - self.started_at) * 1000), 0),
            "finished_elapsed_ms": max(int((finished_at - self.started_at) * 1000), 0),
            "same_arrangement": before_id == after_id if before_id is not None and after_id is not None else None,
            "decoder_executed": decoder_executed, "reference_kind": reference_kind,
        }
        bridge["source_event_id"] = self.record_event(dict(bridge, event_type="reference_capture",
            elapsed_ms=bridge["finished_elapsed_ms"], current_elapsed_ms=bridge["elapsed_ms"]))
        self.bridges.append(bridge)

    def selected_entry(self, objective: str) -> Optional[int]:
        full = self.archive.best_by_objective.get(objective)
        if full is not None:
            return full
        groups = self.archive.partial_groups
        if not groups:
            return None
        scope = min(groups, key=lambda key: (-len(key[0]), -len(key[1])))
        group = groups[scope]
        return group.best_by_objective.get(objective, group.entry_ids[0])

    def sync(self, view: _GoalView) -> None:
        entry_id = self.selected_entry(view.objective)
        revision = self.revisions.get(entry_id, 0) if entry_id is not None else -1
        if entry_id is not None and (view.entry_id != entry_id or view.evidence_revision != revision):
            view.candidate = self.archive.view(entry_id, objective=view.objective)
            view.candidate["_shared_entry_id"] = entry_id
            view.candidate["_shared_evidence_revision"] = revision
            view.entry_id, view.evidence_revision = entry_id, revision
        candidate = view.candidate
        if candidate is None:
            return
        entry = self.archive.entry(cast(int, entry_id))
        view.report.sync_best_reference(candidate, origin=str(entry.evidence_origin["origin"]))
        view.state.best = candidate
        if view.graph_bundle is not None:
            view.graph_bundle.state.best = candidate
            for stage in view.graph_bundle.stages:
                if isinstance(stage, IteratedGreedyStage) and stage.run.search is not None:
                    search = stage.run.search
                    incumbent = search.best
                    if (incumbent is not None and incumbent.get("_shared_entry_id") == entry_id
                            and incumbent.get("_shared_evidence_revision") == revision):
                        # Its own improvement already has the right reference context. Align only
                        # the comparison pointer; a genuine new parent still uses pending_adoption.
                        search.best = candidate
        if view.local_stage is not None:
            view.local_stage.best = candidate

    def run_action(self, view: _GoalView, stage: SearchStage, *, initial: bool = False) -> bool:
        started_at, before_events = self.clock(), len(self.events)
        before_complete = self.first_complete_elapsed_ms
        before_new = self.decode_session.new_decisions if self.decode_session is not None else 0
        before_reused = self.decode_session.reused_decisions if self.decode_session is not None else 0
        self.search_objective, self.phase = view.objective, stage.name
        skip_reason = None
        with self.archive.retention_scope():
            self.sync(view)
            try:
                try:
                    stage.run_task()
                except SharedSearchSkip as skipped:
                    skip_reason = skipped.reason
                # No target's comparison reference changes while a generator decides acceptance.
                for target_view in self.views.values():
                    self.sync(target_view)
            finally:
                self._refresh_active_entries()
            new_events = self.events[before_events:]
        finished_at = self.clock()
        view.stage_charged_seconds[id(stage)] = view.stage_charged_seconds.get(id(stage), 0.0) + max(
            finished_at - started_at, 0.001)
        skip_reason = skip_reason or next((event.get("reason") for event in reversed(new_events)
            if event.get("execution_kind") == "request_skipped" or event.get("event_type") == "decode_skipped"), None)
        new_decisions = (self.decode_session.new_decisions - before_new if self.decode_session is not None
                         else sum(event["verified"] and not event.get("content_reused", False) for event in new_events))
        reused_decisions = (self.decode_session.reused_decisions - before_reused
                            if self.decode_session is not None else 0)
        improvements = list(dict.fromkeys(target for event in new_events for target in event["improved_objectives"]))
        if self.budget is not None:
            self.budget.record_action(view.objective, stage.name, finished_at - started_at,
                new_decisions=new_decisions, reused_decisions=reused_decisions, improved_objectives=improvements,
                first_complete=before_complete is None and self.first_complete_elapsed_ms is not None,
                initial=initial, skip_reason=skip_reason)
        self.actions.append({
            "action_id": len(self.actions) + 1, "search_objective": view.objective,
            "phase": stage.name, "initial_construction": initial,
            "started_elapsed_ms": max(int((started_at - self.started_at) * 1000), 0),
            "finished_elapsed_ms": max(int((finished_at - self.started_at) * 1000), 0),
            "elapsed_ms": max((finished_at - started_at) * 1000.0, 0.0),
            "evaluation_count": sum(event.get("event_type") == "archive_observation" for event in new_events),
            "verified_evaluation_count": sum(event["verified"] and event.get("event_type") == "archive_observation"
                                              for event in new_events),
            "new_decisions": new_decisions, "reused_decisions": reused_decisions, "skip_reason": skip_reason,
            "improved_objectives": improvements,
        })
        return bool(new_events)

    def _refresh_active_entries(self) -> None:
        """Replace archive roots with the candidates that paused generators actually hold."""
        active = set()

        def retain(candidate: Optional[Dict[str, Any]]) -> Optional[int]:
            entry_id = candidate.get("_shared_entry_id") if candidate is not None else None
            if entry_id in self.archive:
                active.add(entry_id)
            return entry_id

        for view in self.views.values():
            current_id = (view.state.best or {}).get("_shared_entry_id")
            if view.local_stage is not None and view.local_stage.local_state is not None:
                current_id = retain(view.local_stage.local_state.current)
            starts: List[int] = []
            if view.graph_bundle is not None:
                for stage in view.graph_bundle.stages:
                    if isinstance(stage, ProfileStage):
                        for elite in stage.pool.elites:
                            retain(elite["candidate"])
                        for elite in stage.pool.active_parents:
                            retain(elite["candidate"])
                    elif isinstance(stage, (RepairStage, IteratedGreedyStage)):
                        for elite in stage.run.pool.elites:
                            retain(elite["candidate"])
                        for elite in stage.run.pool.active_parents:
                            retain(elite["candidate"])
                    if not isinstance(stage, IteratedGreedyStage):
                        continue
                    run = stage.run
                    retain(run.pending_adoption)
                    if run.search is None:
                        continue
                    search = run.search
                    if search.reference is not None:
                        current_id = retain(search.reference.candidate)
                    for entry in search.solution_pool.entries:
                        entry_id = retain(entry.candidate)
                        if entry_id is not None and entry_id not in starts:
                            starts.append(entry_id)
                    for entry in search.decoded_entries.values():
                        retain(entry.candidate)
            self.archive.set_starting_entries(view.objective, starts)
            if current_id is not None:
                self.archive.accept_exploration(view.objective, current_id)
        self.archive.set_active_entries(active)


def _business_neighborhoods(objective: str) -> Tuple[str, ...]:
    first = {
        "min_overdue": ("tardy_window", "time_window"),
        "min_tardiness": ("tardy_window", "time_window"),
        "min_weighted_tardiness": ("tardy_window", "resource_alternative"),
        "min_changeover": ("changeover_block", "resource_alternative"),
    }[objective]
    return first + tuple(neighborhood for neighborhood in BUSINESS_NEIGHBORHOODS if neighborhood not in first)


def _next_stage(view: _GoalView, *, first_opportunity: bool = False) -> Optional[SearchStage]:
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
    *, calendar_service: Any, cfg_svc: Any, cfg: Any, algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any], start_dt: datetime, end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]], seed_results: List[Dict[str, Any]],
    resource_pool: Optional[Dict[str, Any]], version: int, logger: Any = None,
    readiness_gate_enabled: bool = False, strict_mode: bool = False,
    graph_ready_context: Optional[Any] = None, graph_dispatch_mode_override: Optional[str] = None,
    graph_prepare: Optional[Callable[[], Any]] = None, search_budget: Optional[SearchBudget] = None,
    _runtime: Optional[OptimizerRuntime] = None,
) -> SharedOptimizationResult:
    """Construct once, then rotate one action at a time over all target generators."""
    runtime = _resolve_runtime(_runtime, search_budget)
    started_at = runtime.clock()
    algo_stats: Dict[str, Any] = {"fallback_counts": {}, "param_fallbacks": {}}
    cfg = ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))
    if graph_dispatch_mode_override not in (None, "sgs"):
        raise ValidationError("图派工模式覆盖只允许使用 sgs。", field="graph_dispatch_mode_override")
    seeds = coerce_seed_results(seed_results, optimizer_algo_stats=algo_stats)
    scheduler = runtime.scheduler_factory(calendar_service=calendar_service, config_service=cfg, logger=logger)
    config = resolve_optimizer_config(cfg_svc=cfg_svc, snapshot=cfg, optimizer_algo_stats=algo_stats)
    configured_seconds = config.time_budget_seconds
    deadline = started_at + config.time_budget_seconds if config.algo_mode == "improve" else float("inf")
    if search_budget is not None and math.isfinite(search_budget.assigned_seconds):
        deadline = search_budget.deadline
        configured_seconds = search_budget.assigned_seconds
    elif search_budget is not None:
        deadline = min(search_budget.deadline, deadline)
    if runtime.clock() >= deadline:
        raise SearchBudgetExhausted("candidate_time_budget_reached")

    graph_preparation_calls = 0
    if graph_prepare is not None:
        preparation = graph_prepare()
        graph_preparation_calls = 1
        graph_ready_context = preparation.graph_ready_context
        graph_dispatch_mode_override = preparation.graph_dispatch_mode_override
    piece = bool(graph_ready_context is not None and graph_ready_context.get("piece_scope"))
    if any(getattr(op, "piece_id", None) is not None for op in algo_ops_to_schedule) and not piece:
        raise ValidationError("分件排产需要真实工艺依赖图。", field="graph_ready_context")
    ordinary_context = dict(cast(Dict[str, Any], graph_ready_context), score_enabled=False) if piece else None
    forced_sgs = piece or graph_dispatch_mode_override == "sgs"
    dispatch_mode = "sgs" if forced_sgs else config.dispatch_mode
    dispatch_modes = ["sgs"] if forced_sgs else config.dispatch_modes()
    evaluation_context = prepare_evaluation_context(
        batches=batches, expected_operations=algo_ops_to_schedule, seed_results=seeds,
    )
    expected = evaluation_context.expected_keys or frozenset()
    targets = target_objectives_for(config.objective_name)
    archive = SharedScheduleArchive(config.objective_name, targets, (op_id for _, op_id in expected),
                                    set(batches) | {batch_id for batch_id, _ in expected})
    shared_budget = SharedSearchBudget(clock=runtime.clock, started_at=started_at, deadline=deadline,
                                      target_objectives=targets, configured_seconds=configured_seconds)
    session = _SharedSearch(archive=archive, clock=runtime.clock, started_at=started_at, budget=shared_budget)
    session.decode_session = SharedDecodeSession(
        archive=archive, budget=shared_budget, scheduler=scheduler, operations=algo_ops_to_schedule,
        batches=batches, seed_results=seeds, downtime_map=downtime_map, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context, clock=runtime.clock, started_at=started_at, deadline=deadline,
        event_sink=session.record_event, start_dt=start_dt, evaluation_context=evaluation_context)
    native_preparation = session.decode_session.native_preparation

    def build_order(strategy: SortStrategy, params: Dict[str, Any]) -> List[str]:
        sortable = build_batch_sort_inputs(native_preparation.batches,
                                           strict_mode=bool(strict_mode), strategy=strategy,
                                           readiness_gate_enabled=bool(readiness_gate_enabled))
        sorter = StrategyFactory.create(strategy, **(params or {}))
        return [item.batch_id for item in sorter.sort(sortable, base_date=start_dt.date())]

    profile = build_candidate_profile(algo_mode=config.algo_mode, dispatch_mode=dispatch_mode,
        dispatch_rule=config.dispatch_rule, time_budget_seconds=config.time_budget_seconds, version=version,
        strict_mode=bool(strict_mode), ortools_enabled=is_ortools_enabled(cfg), graph_sgs_required=piece)
    for target in targets:
        report = OptimizationSearchReportState(
            algorithm_profile=profile.profile, seed=int(version), time_budget_seconds=config.time_budget_seconds,
            objective_name=target, started_at=started_at,
            candidate_profile=profile.to_report_dict(), candidate_clock=runtime.clock,
            candidate_observer=lambda *, _target=target, **kw: session.observe(_target, **kw),
            candidate_acceptance_observer=lambda *, _target=target, **kw: session.accept(_target, **kw),
            reference_capture_observer=lambda *, _target=target, **kw: session.capture(_target, **kw),
        )
        session.views[target] = _GoalView(target, OptimizerSearchState(), report)
    primary = session.views[targets[0]]
    decode_common: Dict[str, Any] = dict(
        start_dt=start_dt, end_date=end_date, resource_pool=resource_pool, deadline=deadline,
        optimizer_algo_stats=algo_stats, t_begin=started_at, readiness_gate_enabled=bool(readiness_gate_enabled),
        strict_mode=bool(strict_mode), clock=runtime.clock, decode_session=session.decode_session,
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
    graph_enabled = cfg.graph_analysis_mode == "on" and graph_ready_context is not None
    if config.algo_mode == "improve" and graph_enabled and runtime.clock() < deadline:
        graph_construction = {"graph_ready_optimization": graph_ready_v2_profile_summary(
            max_candidate_profiles=60, seed=version, objective_name=targets[0], shared_search=True)}
        feature_preparation_calls = 1
        feature_started_at = runtime.clock()
        try:
            prepared_features = prepare_shared_graph_features(
                **{key: common[key] for key in ("scheduler", "algo_ops_to_schedule", "batches", "start_dt",
                                               "downtime_map", "seed_sr_list", "resource_pool", "deadline", "clock")},
                graph_ready_context=cast(Dict[str, Any], graph_ready_context), candidate_construction=graph_construction)
        except _GraphReadyDeadlineExhausted:
            primary.report.mark_phase_skipped("graph_features", "time_budget")
        finally:
            shared_budget.charge_preparation(targets[0], "graph_features", runtime.clock() - feature_started_at)

    def prepare_view(view: _GoalView) -> None:
        if view.prepared:
            return
        view_started_at = runtime.clock()
        session.search_objective, session.phase = view.objective, "prepare_view"
        session.sync(view)
        view.prepared = True
        if view.objective == targets[0] and profile.ortools_warmstart_enabled:
            def warmstart() -> None:
                view.state.best = runtime.run_ortools_warmstart(
                    **decode_common, scheduler=scheduler, algo_ops_to_schedule=algo_ops_to_schedule, batches=batches,
                    algo_mode=config.algo_mode, cfg=cfg, strategy_enum=config.strategy_enum, objective_name=view.objective,
                    dispatch_mode_cfg=dispatch_mode, dispatch_rule_cfg=config.dispatch_rule,
                    attempts=view.state.attempts, improvement_trace=view.state.improvement_trace, best=view.state.best,
                    logger=logger, graph_ready_context=ordinary_context, search_report_state=view.report)
            view.stages.append(_WarmStartStage(run=warmstart, clock=runtime.clock, deadline=deadline))
        if not piece:
            view.local_stage = LocalSearchStage(
                **decode_common, batches=batches, algo_mode=config.algo_mode, best=view.state.best, version=version,
                dispatch_mode_cfg=dispatch_mode, dispatch_rule_cfg=config.dispatch_rule, objective_name=view.objective,
                attempts=view.state.attempts, improvement_trace=view.state.improvement_trace,
                rng_factory=runtime.rng_factory, search_report_state=view.report,
                neighborhoods=_business_neighborhoods(view.objective),
                valid_dispatch_rules=list(config.valid_dispatch_rules), acceptance=profile.acceptance)
            view.stages.append(view.local_stage)
            view.stages.append(GraspIGStage(
                **decode_common, algo_mode=config.algo_mode, version=version,
                candidate_construction=profile.candidate_construction, base_strategy=config.strategy_enum,
                base_params=config.strategy_params or {}, build_order=build_order, dispatch_rule_cfg=config.dispatch_rule,
                objective_name=view.objective, rng_factory=runtime.rng_factory,
                batch_order_enabled="batch_order" in dispatch_modes, search_report_state=view.report, state=view.state))
        if prepared_features is not None and runtime.clock() < deadline:
            view.graph_bundle = build_graph_search_stages(
                **decode_common, algo_ops_to_schedule=algo_ops_to_schedule,
                algo_mode=config.algo_mode, best=view.state.best,
                version=version, base_strategy=config.strategy_enum, base_params=config.strategy_params or {},
                build_order=build_order, dispatch_rule_cfg=config.dispatch_rule, objective_name=view.objective,
                attempts=view.state.attempts, improvement_trace=view.state.improvement_trace,
                graph_ready_context=graph_ready_context,
                search_report_state=view.report, candidate_construction=graph_construction,
                prepared_features=prepared_features)
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
    attempts = primary.state.compact_attempts(limit=12)
    trajectory = session.trajectories[targets[0]]
    report = primary.report.finalize(runtime_ms=runtime_ms, attempts=attempts,
                                     improvement_trace=trajectory, stop_reason=stop_reason)
    _record_decoder_invocations(report, scheduler)
    outcome = OptimizationOutcome(
        results=best["results"], summary=best["summary"], used_strategy=best["strategy"], used_params=best["params"],
        metrics=best["metrics"], best_score=best["score"], best_order=list(best.get("order") or []),
        attempts=attempts, improvement_trace=trajectory, algo_mode=config.algo_mode, objective_name=targets[0],
        time_budget_seconds=config.time_budget_seconds, algo_stats=best.get("algo_stats") or algo_stats,
        search_report=report, dispatch_mode=str(best.get("dispatch_mode") or dispatch_mode),
        dispatch_rule=(str(best.get("dispatch_rule") or config.dispatch_rule)
                       if best.get("dispatch_mode") == "sgs" else config.dispatch_rule),
    )
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
    return SharedOptimizationResult(archive, outcome, targets, facts)


__all__ = ["SharedOptimizationResult", "optimize_shared_schedule"]
