"""Shared optimizer session state: archive observations, stable target views and action records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .optimizer.graph.ready import GraphStageBundle
from .optimizer.graph.stages import IteratedGreedyStage, ProfileStage, RepairStage
from .optimizer.local_search import LocalSearchStage
from .optimizer.search_report import OptimizationSearchReportState
from .optimizer.search_stage import SearchStage
from .optimizer.search_state import OptimizerSearchState
from .optimizer.shared_archive import ArchiveObservation, CandidateArchiveRef, SharedScheduleArchive
from .optimizer.shared_budget import SharedSearchBudget, SharedSearchSkip
from .optimizer.shared_decode import SharedDecodeSession


@dataclass
class GoalView:
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


class SharedSearch:
    """Own archive observations and refresh stable target views only at action boundaries."""

    def __init__(self, *, archive: SharedScheduleArchive, clock: Callable[[], float], started_at: float,
                 budget: SharedSearchBudget) -> None:
        self.archive, self.clock, self.started_at = archive, clock, started_at
        self.budget = budget
        # The decode session records events through this search, so its owner attaches it right after construction.
        self.decode_session: SharedDecodeSession
        self.views: Dict[str, GoalView] = {}
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
            "strategy": candidate["strategy"].value,
            "repair_decision": candidate.get("repair_decision"),
        }
        if receipt is not None:
            source.update(request_id=receipt["request_id"], source_event_ref=receipt.get("source_event_ref"),
                          execution_kind=receipt["execution_kind"])
        archive_ref: CandidateArchiveRef = candidate["archive_ref"]
        observed: Optional[ArchiveObservation] = archive_ref.take_observation()
        if observed is None:
            if archive_ref.entry_id is None:
                raise ValueError("A decoded candidate must receive its archive identity before reporting.")
            observed = ArchiveObservation(entry_id=archive_ref.entry_id, reused=True,
                                          reason=None if verified else "validation_unknown")
        entry_id = observed.entry_id
        retained = entry_id in self.archive
        if retained and verified:
            self.archive.finish_observation(observed, candidate, origin=source)
        strict_improvements = (list(observed.improved_objectives)
                               if retained and entry_id is not None
                               and self.archive.entry(entry_id).score_scope.is_complete else [])
        if receipt is not None and retained:
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
            entry = self.archive.entry(entry_id)
            event["evaluations"] = {target: {"field_order": list(evaluation.field_order),
                                              "score": list(evaluation.score)}
                                    for target, evaluation in entry.evaluations.items()}
            event["score_scope"] = entry.score_scope
            if not entry.score_scope.is_complete:
                event["partial_group_improved_objectives"] = list(observed.improved_objectives)
            if self.initial_entry_id is None:
                self.initial_entry_id = entry_id
            if entry_id not in self.evidence_event_ids or observed.evidence_updated or observed.restored:
                self.evidence_event_ids[entry_id] = event_id
            if observed.evidence_updated:
                self.revisions[entry_id] = self.revisions.get(entry_id, 0) + 1
            archive_ref.evidence_revision = self.revisions.get(entry_id, 0)
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
        entry_id = candidate["archive_ref"].entry_id
        if entry_id in self.archive:
            self.archive.accept_exploration(objective, entry_id)

    def capture(self, objective: str, *, before: Dict[str, Any], after: Optional[Dict[str, Any]],
                started_at: float, finished_at: float, decoder_executed: bool, reference_kind: str) -> None:
        before_id = before["archive_ref"].entry_id
        after_id = after["archive_ref"].entry_id if after is not None else None
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

    def sync(self, view: GoalView) -> None:
        entry_id = self.selected_entry(view.objective)
        revision = self.revisions.get(entry_id, 0) if entry_id is not None else -1
        if entry_id is not None and (view.entry_id != entry_id or view.evidence_revision != revision):
            view.candidate = self.archive.view(entry_id, objective=view.objective)
            view.candidate["archive_ref"] = CandidateArchiveRef(entry_id, evidence_revision=revision)
            view.entry_id, view.evidence_revision = entry_id, revision
        candidate = view.candidate
        if candidate is None or entry_id is None:
            return
        entry = self.archive.entry(entry_id)
        view.report.sync_best_reference(candidate, origin=str(entry.evidence_origin["origin"]))
        view.state.best = candidate
        if view.graph_bundle is not None:
            view.graph_bundle.state.best = candidate
            for stage in view.graph_bundle.stages:
                if isinstance(stage, IteratedGreedyStage) and stage.run.search is not None:
                    search = stage.run.search
                    incumbent = search.best
                    if (incumbent is not None and incumbent["archive_ref"].entry_id == entry_id
                            and incumbent["archive_ref"].evidence_revision == revision):
                        # Its own improvement already has the right reference context. Align only
                        # the comparison pointer; a genuine new parent still uses pending_adoption.
                        search.best = candidate
        if view.local_stage is not None:
            view.local_stage.best = candidate

    def run_action(self, view: GoalView, stage: SearchStage, *, initial: bool = False) -> None:
        started_at, before_events = self.clock(), len(self.events)
        before_complete = self.first_complete_elapsed_ms
        before_new, before_reused = self.decode_session.new_decisions, self.decode_session.reused_decisions
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
        new_decisions = self.decode_session.new_decisions - before_new
        reused_decisions = self.decode_session.reused_decisions - before_reused
        improvements = list(dict.fromkeys(target for event in new_events for target in event["improved_objectives"]))
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

    def _refresh_active_entries(self) -> None:
        """Replace archive roots with the candidates that paused generators actually hold."""
        active = set()

        def retain(candidate: Optional[Dict[str, Any]]) -> Optional[int]:
            entry_id = candidate["archive_ref"].entry_id if candidate is not None else None
            if entry_id in self.archive:
                active.add(entry_id)
            return entry_id

        for view in self.views.values():
            best = view.state.best
            current_id = best["archive_ref"].entry_id if best is not None else None
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


__all__ = ["GoalView", "SharedSearch"]
