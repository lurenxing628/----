from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable, Dict, Generator, Iterator, List, Optional, Sequence, Set, Tuple, cast

from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.candidate_fingerprint import (
    build_candidate_fingerprint,
    score_strictly_better,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    GraphReadyWeightProfile,
)
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip

from .repair_contract import EliteRepairLimits, new_repair_report
from .repair_decisions import (
    PreparedRepairScope,
    RepairParentPreparation,
    prepare_repair_parent,
    prepare_repair_scope,
)
from .repair_portfolio import ParentRepairPortfolio, RepairPortfolio, build_repair_portfolio
from .repair_rotation import (
    _current_improvements,
    _defer_to_improved_elites,
    _fill_round_slots,
    _fresh_pool_elites,
    _pending_neighbors,
    _prepare_next_repair_round,
    _retain_pending_tail,
    _with_unvisited_pool_elites,
)

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

# A decoded parent's content identity (its archive entry id) and its decoded batch order.
_ParentKey = Tuple[int, Tuple[str, ...]]


class EliteRepairPool:
    """Bounded, decoded v2 elites; all graph outputs remain in the duplicate set."""

    def __init__(self, *, limits: EliteRepairLimits, objective_name: str, operations: List[Any],
                 start_dt: Any, seed: int,
                 best: Optional[Dict[str, Any]], report_state: OptimizationSearchReportState,
                 graph_context: Dict[str, Any],
                 clock: Callable[[], float], deadline: float,
                 decode_session: SharedDecodeSession,
                 decision_features: Any) -> None:
        self.limits = limits
        self.objective_name = objective_name
        self.operations = operations
        self.decision_features = decision_features
        self.start_dt = start_dt
        self.seed = seed
        self.clock = clock
        self.deadline = deadline
        self.scope: PreparedRepairScope = prepare_repair_scope(
            operations,
            graph_context,
            resource_pairs_for=decode_session.native_preparation.qualified_resource_pairs,
        )
        self.elites: List[Dict[str, Any]] = []
        self.active_parents: List[Dict[str, Any]] = []
        self.parents_by_fingerprint: Dict[tuple, Dict[str, Any]] = {}
        self.report_state = report_state
        self.seen_outputs = set(report_state.candidate_fingerprints)
        if best is not None:
            self.seen_outputs.add(self.fingerprint(best).output_key)
        self.seen_elites: set = set()
        self._ig_candidates: Set[_ParentKey] = {self._parent_key(best)} if best is not None else set()
        # Parent preparation is a pure function of the decoded content and decoded batch order under this
        # pool's fixed inputs, so candidates decoding the same content share one preparation whatever their
        # result enumeration order. Each active pair is prepared once and pruned when evicted from active
        # elites/IG references.
        self._prepared_parents: Dict[_ParentKey, RepairParentPreparation] = {}
        self.report = new_repair_report()

    @staticmethod
    def _parent_key(candidate: Dict[str, Any]) -> _ParentKey:
        return cast(int, candidate["archive_ref"].entry_id), tuple(candidate["decoded_batch_order"])

    def fingerprint(self, candidate: Dict[str, Any], parent: Any = None, *, identity: Any = None) -> Any:
        if identity is None:
            identity = self.report_state.fingerprint_identity(candidate)
        if identity is None:
            identity = next((elite["fingerprint"] for elite in self.parents_by_fingerprint.values()
                             if elite["candidate"] is candidate), None)
        return build_candidate_fingerprint(candidate, objective_name=self.objective_name,
                                           parent_fingerprint=parent, seen_output_fingerprints=self.seen_outputs,
                                           identity=identity)

    def observe(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile, *, fingerprint: Any) -> None:
        """Record the decoded output under its fingerprint and maybe adopt it as an elite."""
        self.seen_outputs.add(fingerprint.output_key)
        if profile.formula_version.startswith("graph_ready_v2"):
            self._observe_elite(candidate, profile, fingerprint)

    def _observe_elite(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile, fingerprint: Any) -> None:
        if candidate["summary"].failed_ops or not candidate["summary"].success:
            return
        elite_identity = (profile.feature_basis, fingerprint.output_key)
        if elite_identity in self.seen_elites:
            return
        if self.clock() >= self.deadline:
            self.report["repair_stop_reason"] = "time_budget"
            return
        self.seen_elites.add(elite_identity)
        elite = self.parents_by_fingerprint.get(fingerprint.output_key)
        if elite is None:
            elite = next((parent for parent in self.active_parents
                          if parent.get("fingerprint") is not None
                          and parent["fingerprint"].output_key == fingerprint.output_key), None)
        if elite is not None:
            self.add_basis_variant(elite, profile)
        else:
            elite = self.make_elite(candidate, profile, fingerprint=fingerprint)
        if not elite["neighborhood"].candidate_count:
            self._prune_prepared_parents()
            return
        self.parents_by_fingerprint[fingerprint.output_key] = elite
        self._select_parent_elites()

    def sync_ig_candidates(self, *candidates: Optional[Dict[str, Any]]) -> None:
        self._ig_candidates = {self._parent_key(candidate) for candidate in candidates if candidate is not None}
        self._prune_prepared_parents()

    def _prune_prepared_parents(self) -> None:
        active_ids = set(self._ig_candidates)
        for elite in self.elites:
            active_ids.add(self._parent_key(elite["candidate"]))
        for parent in self.active_parents:
            active_ids.add(self._parent_key(parent["candidate"]))
        for key in list(self._prepared_parents):
            if key not in active_ids:
                del self._prepared_parents[key]

    def prepare_parent(self, candidate: Dict[str, Any]) -> RepairParentPreparation:
        """A decoded parent's static facts, prepared once per candidate; an elite keeps them as ``prepared_parent``."""
        key = self._parent_key(candidate)
        known = self._prepared_parents.get(key)
        if known is not None:
            return known
        prepared = self._prepared_parents[key] = prepare_repair_parent(candidate, scope=self.scope)
        return prepared

    def make_elite(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile, *, fingerprint: Any = None) -> Dict[str, Any]:
        prepared = self.prepare_parent(candidate)
        neighborhood = ParentRepairPortfolio(((profile, self._build_variant(profile, prepared)),))
        resolved_fingerprint = fingerprint if fingerprint is not None else self.fingerprint(candidate)
        return {"candidate": candidate, "profile": profile, "fingerprint": resolved_fingerprint,
                "neighborhood": neighborhood, "decision_offset": 0, "stream_offsets": {}, "prepared_parent": prepared}

    def _build_variant(self, profile: GraphReadyWeightProfile, prepared_parent: RepairParentPreparation) -> RepairPortfolio:
        return build_repair_portfolio(
            operations=self.operations, metrics_by_op_id=self.decision_features.selected_metrics(profile),
            start_dt=self.start_dt, seed=self.seed, objective_name=self.objective_name, prepared_parent=prepared_parent)

    def add_basis_variant(self, elite: Dict[str, Any], profile: GraphReadyWeightProfile) -> None:
        neighborhood = elite["neighborhood"]
        if profile.feature_basis not in neighborhood.feature_bases:
            elite["neighborhood"] = neighborhood.with_variant(
                profile, self._build_variant(profile, elite["prepared_parent"]))

    def _select_parent_elites(self) -> None:
        parents = sorted(self.parents_by_fingerprint.values(), key=lambda elite: (
            tuple(elite["candidate"]["score"]), elite["profile"].profile_order))
        representatives: Dict[str, Dict[str, Any]] = {}
        for elite in parents:
            for basis in elite["neighborhood"].feature_bases:
                representatives.setdefault(basis, elite)
        selected = {id(elite) for elite in list(representatives.values())[:self.limits.top_k]}
        for elite in parents:
            if len(selected) < self.limits.top_k:
                selected.add(id(elite))
        self.elites = [elite for elite in parents if id(elite) in selected]
        self.parents_by_fingerprint = {elite["fingerprint"].output_key: elite for elite in self.elites}
        self._prune_prepared_parents()


class EliteRepairRun:
    """Elite repair as a resumable search stage: one task is one evaluated neighbour."""

    def __init__(self, pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]], budget: Any,
                 deadline: float, clock: Callable[[], float], report_state: OptimizationSearchReportState) -> None:
        self.pool = pool
        self.state = state
        self.evaluate = evaluate
        self.budget = budget
        self.clock = clock
        self.report_state = report_state
        self.report = pool.report
        self.repair_deadline = deadline
        self.exhausted = False
        self.finished = False
        self._tasks: Optional[Generator[None, None, None]] = None

    def available(self) -> bool:
        if self.report["repair_stop_reason"] in ("time_budget", "estimated_decode_cost"):
            return False
        if self.exhausted:
            return (self.clock() < self.repair_deadline
                    and self.report["repair_rounds_completed"] < self.pool.limits.max_rounds
                    and any(_pending_neighbors(elite) > 0 for elite in self.pool.elites))
        if self._tasks is None:
            return bool(self.pool.elites) and self.clock() < self.repair_deadline
        return self.clock() < self.repair_deadline

    def step(self) -> None:
        tasks = self._tasks
        if tasks is None or self.exhausted:
            tasks = self._resume_tasks()
        try:
            next(tasks)
        except StopIteration:
            self.exhausted = True

    def _resume_tasks(self) -> Generator[None, None, None]:
        self.exhausted = False
        self.report["repair_stop_reason"] = None
        self._tasks = _repair_tasks(self.pool, state=self.state, evaluate=self.evaluate,
                                    repair_deadline=self.repair_deadline, clock=self.clock,
                                    report_state=self.report_state,
                                    start_round=self.report["repair_rounds_completed"])
        return self._tasks

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        report = self.report
        if self._tasks is not None:
            self._tasks.close()
            if report["repair_stop_reason"] is None:
                report["repair_stop_reason"] = "time_budget" if self.clock() >= self.repair_deadline else "rotation_ended"
        elif self.pool.elites:
            report["repair_stop_reason"] = "time_budget" if self.clock() >= self.repair_deadline else "rotation_ended"


def _repair_tasks(pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]],
                  repair_deadline: float, clock: Callable[[], float], report_state: OptimizationSearchReportState,
                  start_round: int) -> Generator[None, None, None]:
    try:
        report = pool.report
        elites = [elite for elite in pool.elites if _pending_neighbors(elite) > 0]
        queued_elites: List[Dict[str, Any]] = []
        for round_index in range(start_round, pool.limits.max_rounds):
            # New parents can use vacant slots in this round; overflow waits in the bounded queue.
            elites, queued_elites = _with_unvisited_pool_elites(elites, queued_elites, pool)
            improved_elites: List[Dict[str, Any]] = []
            deferred_elites: List[Dict[str, Any]] = []
            for elite_index, elite in enumerate(elites):
                yield from _repair_one_elite(
                    pool, elite=elite, state=state, evaluate=evaluate,
                    report_state=report_state, improved_elites=improved_elites,
                    active_groups=(elites, queued_elites, deferred_elites, improved_elites))
                if report["repair_stop_reason"] in ("estimated_decode_cost", "time_budget"):
                    break
                if _defer_to_improved_elites(pool, round_index, _current_improvements(improved_elites, state.best)):
                    _retain_pending_tail(elite, deferred_elites)
                    deferred_elites.extend(elites[elite_index + 1:])
                    break
                _retain_pending_tail(elite, deferred_elites)
                _fill_round_slots(elites, queued_elites, deferred_elites, pool)
            if report["repair_stop_reason"] in ("estimated_decode_cost", "time_budget"):
                break
            deferred_elites.extend(_fresh_pool_elites(pool, elites, deferred_elites, queued_elites))
            deferred_elites.extend(queued_elites)
            # Give retained parents their first visit before resuming another tail;
            # sharing basis variants must not consume all slots on the first parent.
            deferred_elites.sort(key=lambda elite: bool(elite["decision_offset"]))
            report["repair_rounds_completed"] = round_index + 1
            current_improvements = _current_improvements(improved_elites, state.best)
            if clock() >= repair_deadline:
                report["repair_stop_reason"] = "time_budget"
            elif not current_improvements and not deferred_elites:
                report["repair_stop_reason"] = "no_improvement"
            elif round_index + 1 >= pool.limits.max_rounds:
                report["repair_stop_reason"] = "max_rounds"
            else:
                next_round = _prepare_next_repair_round(
                    pool, improved_elites=current_improvements, deferred_elites=deferred_elites,
                    repair_deadline=repair_deadline, clock=clock)
                if next_round is None:
                    report["repair_stop_reason"] = "time_budget"
                    break
                elites, queued_elites = next_round
                continue
            break
    finally:
        pool.active_parents.clear()
        pool._prune_prepared_parents()


def _repair_one_elite(pool: EliteRepairPool, *, elite: Dict[str, Any], state: Any,
                      evaluate: Callable[..., Dict[str, Any]],
                      report_state: OptimizationSearchReportState,
                      improved_elites: List[Dict[str, Any]],
                      active_groups: Sequence[List[Dict[str, Any]]]) -> Iterator[None]:
    """Visit one elite's neighbours; yields after every evaluated neighbour so the rotation can interleave."""
    report = pool.report
    neighborhood = elite["neighborhood"]
    generated = 0
    offset = elite["decision_offset"]
    # Each basis variant resumes after its own consumed prefix: a variant added between visits must not
    # re-yield decisions this elite already generated nor skip ones it has not.
    consumed: Dict[str, int] = elite["stream_offsets"]
    decisions = iter(neighborhood.profiled_decisions(skip_by_basis=consumed))
    while generated < pool.limits.max_neighbors_per_elite:
        try:
            kind, decision, variant_profile = next(decisions)
        except StopIteration:
            break
        generated += 1
        consumed[variant_profile.feature_basis] = consumed.get(variant_profile.feature_basis, 0) + 1
        elite["decision_offset"] = offset + generated
        _set_active_repair_parents(pool, active_groups)
        profile = replace(variant_profile, slug="v2_repair_" + kind, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                          candidate_policy="elite_repair")
        try:
            candidate = evaluate(profile=profile, order=list(decision.batch_order),
                                 repair=(decision, elite["prepared_parent"]))
        except SharedSearchSkip as exc:
            if exc.reason in ("estimated_decode_cost", "time_budget"):
                report["repair_stop_reason"] = exc.reason
                return
            yield
            continue
        reference = state.best
        fingerprint = pool.fingerprint(candidate, elite["fingerprint"])
        accepted = _can_accept_neighbor(pool, candidate=candidate, best=reference, report_state=report_state,
                                        fingerprint=fingerprint)
        if accepted:
            report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                                                 fingerprint=fingerprint)
            state.best = candidate
            improved_elites.append({"candidate": candidate, "profile": profile,
                                    "basis_profiles": tuple(item[0] for item in neighborhood.variants)})
        yield


def _set_active_repair_parents(pool: EliteRepairPool, groups: Sequence[List[Dict[str, Any]]]) -> None:
    active: Dict[int, Dict[str, Any]] = {}
    for group in groups:
        for parent in group:
            active[id(parent)] = parent
    pool.active_parents = list(active.values())
    pool._prune_prepared_parents()


def _can_accept_neighbor(pool: EliteRepairPool, *, candidate: Dict[str, Any],
                         best: Optional[Dict[str, Any]], report_state: OptimizationSearchReportState,
                         fingerprint: Any) -> bool:
    pool.seen_outputs.add(fingerprint.output_key)
    report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN, fingerprint=fingerprint)
    if fingerprint.same_as_parent or fingerprint.same_as_seen:
        return False
    if candidate["summary"].failed_ops or not candidate["summary"].success:
        return False
    if not score_strictly_better(candidate["score"], (best or {}).get("score")):
        return False
    return candidate_is_preferred(
        candidate=candidate, incumbent=best, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
        incumbent_origin=str((best or {}).get("candidate_origin") or "baseline"),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=report_state.best_fingerprint_changed(),
    )
