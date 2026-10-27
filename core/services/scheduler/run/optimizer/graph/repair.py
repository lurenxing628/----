from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable, Dict, Generator, Iterator, List, Optional, Sequence, Tuple

from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.candidate_fingerprint import (
    build_candidate_fingerprint,
    score_strictly_better,
)
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import select_profile_metrics
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    GraphReadyWeightProfile,
)
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip

from .repair_accounting import RepairWorkAccounting
from .repair_contract import REPAIR_PHASE, EliteRepairLimits, finish_repair_report, new_repair_report
from .repair_decisions import RepairParentPreparation, prepare_repair_parent
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
from .reporting import append_graph_attempt, append_graph_trace

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession


class EliteRepairPool:
    """Bounded, decoded v2 elites; all graph outputs remain in the duplicate set."""

    def __init__(self, *, limits: EliteRepairLimits, objective_name: str, operations: List[Any],
                 metrics_by_op_id: Dict[int, Dict[str, Any]], start_dt: Any, seed: int,
                 best: Optional[Dict[str, Any]], report_state: OptimizationSearchReportState,
                 graph_context: Dict[str, Any],
                 clock: Callable[[], float], deadline: float,
                 decode_session: SharedDecodeSession) -> None:
        self.limits = limits
        self.objective_name = objective_name
        self.operations = operations
        self.metrics_by_op_id = metrics_by_op_id
        self.start_dt = start_dt
        self.seed = seed
        self.graph_context = graph_context
        self.clock = clock
        self.deadline = deadline
        self.decode_session = decode_session
        self.elites: List[Dict[str, Any]] = []
        self.active_parents: List[Dict[str, Any]] = []
        self.parents_by_fingerprint: Dict[tuple, Dict[str, Any]] = {}
        self.profile_parent_sizes: Dict[int, int] = {}
        self._next_portfolio_id = 1
        self.report_state = report_state
        self.seen_outputs = set(report_state.candidate_fingerprints)
        if best is not None:
            self.seen_outputs.add(self.fingerprint(best).output_key)
        self.seen_elites: set = set()
        # Parent preparation is a pure function of the decoded candidate under this pool's fixed inputs; each
        # candidate object is prepared once. The entry pins the candidate, so its ``id`` cannot be reused.
        self._prepared_parents: Dict[int, Tuple[Dict[str, Any], RepairParentPreparation]] = {}
        self.report = new_repair_report(limits, objective_name=objective_name)

    def fingerprint(self, candidate: Dict[str, Any], parent: Any = None, *, identity: Any = None) -> Any:
        if identity is None:
            identity = self.report_state.fingerprint_identity(candidate)
        if identity is None:
            identity = next((elite["fingerprint"] for elite in self.parents_by_fingerprint.values()
                             if elite["candidate"] is candidate), None)
        return build_candidate_fingerprint(candidate, objective_name=self.objective_name,
                                           parent_fingerprint=parent, seen_output_fingerprints=self.seen_outputs,
                                           identity=identity)

    def observe(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> Any:
        """Record the decoded output and maybe adopt it as an elite; returns its fingerprint against earlier outputs."""
        fingerprint = self.fingerprint(candidate)
        self.seen_outputs.add(fingerprint.output_key)
        if profile.formula_version.startswith("graph_ready_v2"):
            self._observe_elite(candidate, profile, fingerprint)
        return fingerprint

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
            return
        self.parents_by_fingerprint[fingerprint.output_key] = elite
        self.profile_parent_sizes[elite["portfolio_id"]] = elite["neighborhood"].candidate_count
        self._select_parent_elites()

    def prepare_parent(self, candidate: Dict[str, Any]) -> RepairParentPreparation:
        """A decoded parent's static facts, prepared once per candidate; an elite keeps them as ``prepared_parent``."""
        known = self._prepared_parents.get(id(candidate))
        if known is not None:
            return known[1]
        prepared = prepare_repair_parent(candidate, self.operations, self.graph_context,
                                         resource_pairs_for=self.decode_session.native_preparation.qualified_resource_pairs)
        self._prepared_parents[id(candidate)] = (candidate, prepared)
        return prepared

    def make_elite(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile, *, fingerprint: Any = None) -> Dict[str, Any]:
        prepared = self.prepare_parent(candidate)
        neighborhood = ParentRepairPortfolio(((profile, self._build_variant(profile, prepared)),))
        resolved_fingerprint = fingerprint if fingerprint is not None else self.fingerprint(candidate)
        elite = {"candidate": candidate, "profile": profile, "fingerprint": resolved_fingerprint,
                 "neighborhood": neighborhood, "decision_offset": 0, "stream_offsets": {}, "prepared_parent": prepared}
        elite["portfolio_id"] = self._next_portfolio_id
        self._next_portfolio_id += 1
        return elite

    def _build_variant(self, profile: GraphReadyWeightProfile, prepared_parent: RepairParentPreparation) -> RepairPortfolio:
        return build_repair_portfolio(
            operations=self.operations, metrics_by_op_id=select_profile_metrics(self.metrics_by_op_id, profile=profile),
            start_dt=self.start_dt, seed=self.seed, objective_name=self.objective_name, prepared_parent=prepared_parent)

    def add_basis_variant(self, elite: Dict[str, Any], profile: GraphReadyWeightProfile) -> None:
        neighborhood = elite["neighborhood"]
        if profile.feature_basis not in neighborhood.feature_bases:
            updated = neighborhood.with_variant(
                profile, self._build_variant(profile, elite["prepared_parent"]))
            elite["neighborhood"] = updated
            portfolio_id = elite.get("portfolio_id")
            if portfolio_id in self.profile_parent_sizes:
                self.profile_parent_sizes[int(portfolio_id)] = updated.candidate_count

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


class EliteRepairRun:
    """Elite repair as a resumable search stage: one task is one evaluated neighbour.

    The shared decode session owns admission and reuse. Rotation and round limits
    keep repair resumable while its report accounts for actual decodes and skips.
    """

    def __init__(self, pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]], budget: Any,
                 deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                 improvement_trace: List[Dict[str, Any]], report_state: OptimizationSearchReportState) -> None:
        self.pool = pool
        self.state = state
        self.evaluate = evaluate
        self.budget = budget
        self.deadline = deadline
        self.clock = clock
        self.t_begin = t_begin
        self.attempts = attempts
        self.improvement_trace = improvement_trace
        self.report_state = report_state
        self.report = pool.report
        self.repair_deadline = deadline
        self.last_task_end: Optional[float] = None
        self.task_seconds = 0.0
        self.exhausted = False
        self.finished = False
        self._tasks: Optional[Generator[None, None, None]] = None
        self.accounting = RepairWorkAccounting()

    def available(self) -> bool:
        if self.report["repair_stop_reason"] in ("time_budget", "estimated_decode_cost"):
            return False
        if self.exhausted:
            return (self.clock() < self.repair_deadline
                    and self.report["repair_rounds_completed"] < self.pool.limits.max_rounds
                    and any(_pending_neighbors(elite) > 0 for elite in self.pool.elites))
        if self._tasks is None:
            return bool(self.pool.elites) and self.clock() < self.deadline
        return self.clock() < self.repair_deadline

    def step(self) -> None:
        started = self.clock()
        tasks = self._tasks
        if tasks is None:
            tasks = self._start(started)
        elif self.exhausted:
            tasks = self._resume_tasks()
        try:
            next(tasks)
        except StopIteration:
            self.exhausted = True
        finished = self.clock()
        self.task_seconds += max(finished - started, 0.0)
        self.last_task_end = finished

    def _start(self, started: float) -> Generator[None, None, None]:
        report, pruning = self.report, self.report["repair_pruning_report"]
        budget_ms = max(int((self.deadline - started) * 1000), 0)
        self.repair_deadline = min(self.deadline, started + budget_ms / 1000.0)
        report["repair_time_budget_ms"] = pruning["budget_ms"] = budget_ms
        report["repair_candidate_budget"] = None
        self.accounting.observe(self.pool.elites)
        report["repair_best_origin"] = (self.state.best or {}).get("candidate_origin")

        return self._resume_tasks()

    def _resume_tasks(self) -> Generator[None, None, None]:
        self.exhausted = False
        self.report["repair_stop_reason"] = None
        self._tasks = _repair_tasks(self.pool, state=self.state, evaluate=self.evaluate, budget=self.budget,
                                    repair_deadline=self.repair_deadline, clock=self.clock, t_begin=self.t_begin,
                                    attempts=self.attempts, improvement_trace=self.improvement_trace,
                                    report_state=self.report_state, accounting=self.accounting,
                                    start_round=self.report["repair_rounds_completed"])
        return self._tasks

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        report, pruning = self.report, self.report["repair_pruning_report"]
        if self._tasks is not None:
            # Closing a suspended generator runs no further neighbour decode. Account from the
            # materialized portfolios even when its code after the last yield never executed.
            self._tasks.close()
            if report["repair_stop_reason"] is None:
                if self.clock() >= self.repair_deadline:
                    report["repair_stop_reason"] = "time_budget"
                else:
                    report["repair_stop_reason"] = "rotation_ended"
        self.accounting.finish(self.pool)
        if self._tasks is None:
            if self.pool.elites:
                # Elites existed, but the rotation never reached this stage before the deadline or the cap.
                report["repair_stop_reason"] = "time_budget" if self.clock() >= self.deadline else "rotation_ended"
                report["repair_status"] = "skipped_by_budget"
            else:
                budget_stopped = (
                    report["repair_stop_reason"] in ("time_budget", "estimated_decode_cost")
                    or self.budget.stop_reason in ("time_budget", "estimated_decode_cost")
                )
                report["repair_status"] = "skipped_by_budget" if budget_stopped else "skipped_no_elite"
        else:
            report["repair_status"] = _repair_status(report)
        pruning["runtime_ms"] = int(self.task_seconds * 1000)
        last = self.last_task_end if self.last_task_end is not None else self.clock()
        report["deadline_overrun_ms"] = max(int((last - self.repair_deadline) * 1000), 0) if self._tasks is not None else 0
        finish_repair_report(report)
        _publish_report(report, attempts=self.attempts)


def _repair_tasks(pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]], budget: Any,
                  repair_deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                  improvement_trace: List[Dict[str, Any]], report_state: OptimizationSearchReportState,
                  accounting: RepairWorkAccounting, start_round: int) -> Generator[None, None, None]:
    try:
        report = pool.report
        pruning = report["repair_pruning_report"]
        def before_decode() -> None:
            pruning["evaluated_candidates"] += 1
            budget.repair_decodes += 1

        elites = [elite for elite in pool.elites if _pending_neighbors(elite) > 0]
        queued_elites: List[Dict[str, Any]] = []
        for round_index in range(start_round, pool.limits.max_rounds):
            # New parents can use vacant slots in this round; overflow waits in the bounded queue.
            elites, queued_elites = _with_unvisited_pool_elites(elites, queued_elites, pool)
            accounting.observe(elites + queued_elites)
            improved_elites: List[Dict[str, Any]] = []
            deferred_elites: List[Dict[str, Any]] = []
            for elite_index, elite in enumerate(elites):
                yield from _repair_one_elite(
                    pool, elite=elite, state=state, evaluate=evaluate,
                    clock=clock, t_begin=t_begin, attempts=attempts,
                    improvement_trace=improvement_trace, report_state=report_state,
                    before_decode=before_decode, improved_elites=improved_elites,
                    accounting=accounting,
                    active_groups=(elites, queued_elites, deferred_elites, improved_elites))
                if report["repair_stop_reason"] in ("estimated_decode_cost", "time_budget"):
                    break
                if _defer_to_improved_elites(pool, elites, elite_index, round_index, _current_improvements(improved_elites, state.best)):
                    _retain_pending_tail(elite, deferred_elites)
                    deferred_elites.extend(elites[elite_index + 1:])
                    break
                _retain_pending_tail(elite, deferred_elites)
                _fill_round_slots(elites, queued_elites, deferred_elites, pool)
                accounting.observe(elites + queued_elites)
            if report["repair_stop_reason"] in ("estimated_decode_cost", "time_budget"):
                break
            deferred_elites.extend(_fresh_pool_elites(pool, elites, deferred_elites, queued_elites))
            deferred_elites.extend(queued_elites)
            accounting.observe(deferred_elites)
            # Give retained parents their first visit before resuming another tail;
            # sharing basis variants must not consume all slots on the first parent.
            deferred_elites.sort(key=lambda elite: bool(elite.get("decision_offset", 0)))
            report["repair_rounds_completed"] = round_index + 1
            report["repair_round_improvements"].append(len(improved_elites))
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
                    repair_deadline=repair_deadline, clock=clock, accounting=accounting)
                if next_round is None:
                    report["repair_stop_reason"] = "time_budget"
                    break
                elites, queued_elites = next_round
                continue
            break
    finally:
        pool.active_parents.clear()


def _repair_one_elite(pool: EliteRepairPool, *, elite: Dict[str, Any], state: Any,
                      evaluate: Callable[..., Dict[str, Any]],
                      clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                      improvement_trace: List[Dict[str, Any]], report_state: OptimizationSearchReportState,
                      before_decode: Callable[[], None],
                      improved_elites: List[Dict[str, Any]],
                      accounting: RepairWorkAccounting,
                      active_groups: Sequence[List[Dict[str, Any]]] = ()) -> Iterator[None]:
    """Visit one elite's neighbours; yields after every evaluated neighbour so the rotation can interleave."""
    report = pool.report
    pruning = report["repair_pruning_report"]
    neighborhood = elite["neighborhood"]
    generated = 0
    offset = elite.get("decision_offset", 0)
    # Each basis variant resumes after its own consumed prefix: a variant added between visits must not
    # re-yield decisions this elite already generated nor skip ones it has not.
    consumed: Dict[str, int] = elite.setdefault("stream_offsets", {})
    decisions = iter(neighborhood.profiled_decisions(skip_by_basis=consumed))
    while generated < pool.limits.max_neighbors_per_elite:
        try:
            kind, decision, variant_profile = next(decisions)
        except StopIteration:
            break
        generated += 1
        consumed[variant_profile.feature_basis] = consumed.get(variant_profile.feature_basis, 0) + 1
        elite["decision_offset"] = offset + generated
        pruning["generated_candidates"] += 1
        accounting.observe((elite,))
        _set_active_repair_parents(pool, active_groups)
        profile = replace(variant_profile, slug="v2_repair_" + kind, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                          candidate_policy="elite_repair")
        try:
            candidate = evaluate(profile=profile, order=list(decision.batch_order),
                                 repair=(decision, elite["prepared_parent"]), before_decode=before_decode)
        except SharedSearchSkip as exc:
            counts = pruning.setdefault("shared_skip_by_reason", {})
            counts[exc.reason] = counts.get(exc.reason, 0) + 1
            if exc.reason in ("estimated_decode_cost", "time_budget"):
                report["repair_stop_reason"] = exc.reason
                return
            yield
            continue
        if candidate["decode_receipt"]["actual_decoder_calls"] == 0:
            pruning["evaluated_candidates"] += 1
            pruning["reused_candidates"] = pruning.get("reused_candidates", 0) + 1
        reference = state.best
        fingerprint = pool.fingerprint(candidate, elite["fingerprint"])
        accepted = _can_accept_neighbor(pool, candidate=candidate, best=reference, report_state=report_state,
                                        fingerprint=fingerprint)
        append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile, reference=reference,
                             accepted=accepted, search_report_state=report_state, clock=clock, t_begin=t_begin)
        if accepted:
            report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                                                 fingerprint=fingerprint)
            append_graph_trace(improvement_trace=improvement_trace, candidate=candidate, profile=profile, clock=clock, t_begin=t_begin)
            report["repair_accepted"] = True
            report["repair_best_origin"] = GRAPH_READY_V2_REPAIRED_ORIGIN
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


def _can_accept_neighbor(pool: EliteRepairPool, *, candidate: Dict[str, Any],
                         best: Optional[Dict[str, Any]], report_state: OptimizationSearchReportState,
                         fingerprint: Any) -> bool:
    pruning = pool.report["repair_pruning_report"]
    pool.seen_outputs.add(fingerprint.output_key)
    report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN, fingerprint=fingerprint)
    if _reject_duplicate_output(pruning, fingerprint):
        return False
    if candidate["summary"].failed_ops or not candidate["summary"].success:
        _reject(pruning, "repair_infeasible")
        return False
    if not score_strictly_better(candidate["score"], (best or {}).get("score")):
        _reject(pruning, "no_strict_improvement")
        return False
    if not candidate_is_preferred(candidate=candidate, incumbent=best, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                                  incumbent_origin=str((best or {}).get("candidate_origin") or "baseline"),
                                  candidate_fingerprint=fingerprint,
                                  incumbent_fingerprint_changed=report_state.best_fingerprint_changed()):
        _reject(pruning, "acceptance_rejected")
        return False
    return True


def _reject_duplicate_output(pruning: Dict[str, Any], fingerprint: Any) -> bool:
    if not (fingerprint.same_as_parent or fingerprint.same_as_seen):
        return False
    pruning["same_fingerprint_rejected"] += 1
    pruning["duplicate_output_rejected"] += 1
    _reject(pruning, "same_fingerprint")
    return True


def _reject(pruning: Dict[str, Any], reason: str) -> None:
    pruning["rejected_candidates"] += 1
    reasons = pruning["rejected_by_reason"]
    reasons[reason] = reasons.get(reason, 0) + 1


def _repair_status(report: Dict[str, Any]) -> str:
    pruning = report["repair_pruning_report"]
    if report["repair_accepted"]:
        return "strict_improvement"
    if not pruning["evaluated_candidates"]:
        exhausted = pruning["skipped_by_budget"] or report["repair_stop_reason"] in {
            "time_budget", "estimated_decode_cost",
        }
        return "skipped_by_budget" if exhausted else "no_strict_improvement"
    if pruning["rejected_candidates"] == pruning["evaluated_candidates"] and not pruning["rejected_by_reason"].get("no_strict_improvement"):
        return "all_candidates_rejected"
    return "no_strict_improvement"


def _publish_report(report: Dict[str, Any], *, attempts: List[Dict[str, Any]]) -> None:
    # Existing public projection keeps profile.message; raw attempts remain diagnostics-only.
    attempts.append({"tag": REPAIR_PHASE, "candidate_status": "phase_summary", "elite_repair": report})
