from __future__ import annotations

from dataclasses import replace
from itertools import islice
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional

from core.infrastructure.errors import ValidationError

from .optimizer_candidate_comparison import candidate_is_preferred
from .optimizer_candidate_fingerprint import build_candidate_fingerprint
from .optimizer_graph_ready_acceptance import build_graph_ready_improve_only_acceptance_event
from .optimizer_graph_ready_context import reason_from_validation
from .optimizer_graph_ready_feature_basis import select_profile_metrics
from .optimizer_graph_ready_profiles import GRAPH_READY_V2_REPAIRED_ORIGIN, GraphReadyWeightProfile
from .optimizer_graph_ready_repair_accounting import RepairWorkAccounting
from .optimizer_graph_ready_repair_contract import (
    REPAIR_PHASE,
    EliteRepairLimits,
    finish_repair_report,
    new_repair_report,
)
from .optimizer_graph_ready_repair_decisions import RepairDecision
from .optimizer_graph_ready_repair_portfolio import ParentRepairPortfolio, RepairPortfolio, build_repair_portfolio
from .optimizer_graph_ready_repair_rotation import (
    _current_improvements,
    _defer_to_improved_elites,
    _fill_round_slots,
    _fresh_pool_elites,
    _pending_neighbors,
    _prepare_next_repair_round,
    _retain_pending_tail,
    _with_unvisited_pool_elites,
)
from .optimizer_graph_ready_reporting import (
    append_graph_attempt,
    append_graph_trace,
    record_rejected_attempt,
    repair_public_message,
)
from .optimizer_graph_ready_v2_contract import is_graph_ready_v2_contract_error


class _RepairBudgetExhausted(RuntimeError):
    pass


class EliteRepairPool:
    """Bounded, decoded v2 elites; all graph outputs remain in the duplicate set."""

    def __init__(self, *, limits: EliteRepairLimits, objective_name: str, operations: List[Any],
                 metrics_by_op_id: Dict[int, Dict[str, Any]], start_dt: Any, seed: int,
                 best: Optional[Dict[str, Any]], report_state: Any,
                 graph_context: Optional[Dict[str, Any]] = None,
                 resource_pool: Optional[Dict[str, Any]] = None,
                 clock: Optional[Callable[[], float]] = None, deadline: Optional[float] = None) -> None:
        self.limits = limits
        self.objective_name = objective_name
        self.operations = operations
        self.metrics_by_op_id = metrics_by_op_id
        self.start_dt = start_dt
        self.seed = seed
        self.graph_context = graph_context
        self.resource_pool = resource_pool
        self.clock = clock
        self.deadline = deadline
        self.elites: List[Dict[str, Any]] = []
        self.parents_by_fingerprint: Dict[str, Dict[str, Any]] = {}
        self.seen_outputs = set(report_state.candidate_fingerprints) if report_state is not None else set()
        if best is not None:
            self.seen_outputs.add(self.fingerprint(best).output_fingerprint)
        self.seen_elites: set = set()
        self.report = new_repair_report(limits, objective_name=objective_name)

    def fingerprint(self, candidate: Dict[str, Any], parent: Optional[str] = None) -> Any:
        return build_candidate_fingerprint(candidate, objective_name=self.objective_name,
                                           parent_fingerprint=parent, seen_output_fingerprints=self.seen_outputs)

    def observe(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> None:
        fingerprint = self.fingerprint(candidate)
        self.seen_outputs.add(fingerprint.output_fingerprint)
        if not self.limits.enabled or not profile.formula_version.startswith("graph_ready_v2"):
            return
        if candidate["summary"].failed_ops or not candidate["summary"].success:
            return
        elite_identity = (profile.feature_basis, fingerprint.output_fingerprint)
        if elite_identity in self.seen_elites:
            return
        if self.clock is not None and self.deadline is not None and self.clock() >= self.deadline:
            self.report["repair_stop_reason"] = "time_budget"
            return
        self.seen_elites.add(elite_identity)
        elite = self.parents_by_fingerprint.get(fingerprint.output_fingerprint)
        if elite is not None:
            self.add_basis_variant(elite, profile)
        else:
            elite = self.make_elite(candidate, profile)
        if not elite["neighborhood"].candidate_count:
            return
        self.parents_by_fingerprint[fingerprint.output_fingerprint] = elite
        self._select_parent_elites()

    def make_elite(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> Dict[str, Any]:
        neighborhood = ParentRepairPortfolio(((profile, self._build_variant(candidate, profile)),))
        return {"candidate": candidate, "profile": profile, "fingerprint": self.fingerprint(candidate),
                "neighborhood": neighborhood, "decision_offset": 0}

    def _build_variant(self, candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> RepairPortfolio:
        return build_repair_portfolio(
            candidate, operations=self.operations, metrics_by_op_id=select_profile_metrics(self.metrics_by_op_id, profile=profile),
            start_dt=self.start_dt, seed=self.seed, objective_name=self.objective_name,
            graph_context=self.graph_context, resource_pool=self.resource_pool)

    def add_basis_variant(self, elite: Dict[str, Any], profile: GraphReadyWeightProfile) -> None:
        neighborhood = elite["neighborhood"]
        if profile.feature_basis not in neighborhood.feature_bases:
            elite["neighborhood"] = neighborhood.with_variant(profile, self._build_variant(elite["candidate"], profile))

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
        removed = [elite for elite in parents if id(elite) not in selected]
        self.report["eligible_elites"] = len(parents)
        self.report["skipped_elites_by_top_k"] = len(removed)
        self.report["skipped_neighbors_by_top_k"] = sum(elite["neighborhood"].candidate_count for elite in removed)


class EliteRepairRun:
    """Elite repair as a resumable search stage: one task is one evaluated neighbour.

    The rotation hands the stage a task whenever it has used the least time; the stage itself only
    keeps its own guards (local time budget, the shared candidate cap, round policy) and reports
    what it evaluated, pruned and skipped exactly as the sequential version did.
    """

    def __init__(self, pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]], budget: Any,
                 deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                 improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool) -> None:
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
        self.strict_mode = strict_mode
        self.report = pool.report
        self.repair_deadline = deadline
        self.started_at: Optional[float] = None
        self.last_task_end: Optional[float] = None
        self.task_seconds = 0.0
        self.exhausted = False
        self.finished = False
        self._tasks: Optional[Generator[None, None, None]] = None
        self.accounting = RepairWorkAccounting()
        self.seen_decisions: set = set()

    def available(self) -> bool:
        if not self.pool.limits.enabled:
            return False
        if self.budget.remaining_candidates() <= 0:
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
        if self._tasks is None:
            self._start(started)
        elif self.exhausted:
            self._resume_tasks()
        try:
            next(self._tasks)
        except StopIteration:
            self.exhausted = True
        finished = self.clock()
        self.task_seconds += max(finished - started, 0.0)
        self.last_task_end = finished

    def _start(self, started: float) -> None:
        report, pruning = self.report, self.report["repair_pruning_report"]
        limits = self.pool.limits
        self.started_at = started
        remaining_ms = max(int((self.deadline - started) * 1000), 0)
        budget_ms = remaining_ms if limits.time_budget_ms is None else min(remaining_ms, limits.time_budget_ms)
        self.repair_deadline = min(self.deadline, started + budget_ms / 1000.0)
        report["repair_time_budget_ms"] = pruning["budget_ms"] = budget_ms
        report["repair_candidate_budget"] = self.budget.remaining_candidates()
        self.accounting.observe(self.pool.elites)
        report["repair_best_origin"] = (self.state.best or {}).get("candidate_origin")

        self._resume_tasks()

    def _resume_tasks(self) -> None:
        self.exhausted = False
        self.report["repair_stop_reason"] = None
        self._tasks = _repair_tasks(self.pool, state=self.state, evaluate=self.evaluate, budget=self.budget,
                                    repair_deadline=self.repair_deadline, clock=self.clock, t_begin=self.t_begin,
                                    attempts=self.attempts, improvement_trace=self.improvement_trace,
                                    report_state=self.report_state, strict_mode=self.strict_mode, accounting=self.accounting,
                                    start_round=self.report["repair_rounds_completed"], seen_decisions=self.seen_decisions)

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
                elif self.budget.remaining_candidates() <= 0:
                    report["repair_stop_reason"] = "candidate_budget"
                else:
                    report["repair_stop_reason"] = "rotation_ended"
        self.accounting.finish(self.pool)
        if not self.pool.limits.enabled:
            report["repair_status"] = "not_run"
        elif self._tasks is None:
            if self.pool.elites:
                # Elites existed, but the rotation never reached this stage before the deadline or the cap.
                report["repair_stop_reason"] = "time_budget" if self.clock() >= self.deadline else "candidate_budget"
                report["repair_status"] = "skipped_by_budget"
            else:
                report["repair_status"] = "skipped_by_budget" if report["repair_stop_reason"] == "time_budget" else "skipped_no_elite"
        else:
            report["repair_status"] = _repair_status(report)
        pruning["runtime_ms"] = int(self.task_seconds * 1000)
        last = self.last_task_end if self.last_task_end is not None else self.clock()
        report["deadline_overrun_ms"] = max(int((last - self.repair_deadline) * 1000), 0) if self._tasks is not None else 0
        finish_repair_report(report)
        _publish_report(report, report_state=self.report_state, attempts=self.attempts)
        if self.report_state is not None and last >= self.deadline:
            self.report_state.mark_deadline_reached()


def _repair_tasks(pool: EliteRepairPool, *, state: Any, evaluate: Callable[..., Dict[str, Any]], budget: Any,
                  repair_deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                  improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool,
                  accounting: RepairWorkAccounting, start_round: int, seen_decisions: set) -> Generator[None, None, None]:
    report = pool.report
    pruning = report["repair_pruning_report"]
    def before_decode() -> None:
        if clock() >= repair_deadline or budget.remaining_candidates() <= 0:
            raise _RepairBudgetExhausted()
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
                pool, elite=elite, elite_index=elite_index, state=state, evaluate=evaluate, budget=budget,
                repair_deadline=repair_deadline, clock=clock, t_begin=t_begin, attempts=attempts,
                improvement_trace=improvement_trace, report_state=report_state, strict_mode=strict_mode,
                before_decode=before_decode, seen_decisions=seen_decisions, improved_elites=improved_elites)
            if _defer_to_improved_elites(pool, elites, elite_index, round_index, _current_improvements(improved_elites, state.best)):
                _retain_pending_tail(elite, deferred_elites)
                deferred_elites.extend(elites[elite_index + 1:])
                for deferred in deferred_elites:
                    deferred["pending_tail"] = True
                break
            _retain_pending_tail(elite, deferred_elites)
            _fill_round_slots(elites, queued_elites, deferred_elites, pool)
            accounting.observe(elites + queued_elites)
        deferred_elites.extend(_fresh_pool_elites(elites + deferred_elites + queued_elites, pool))
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
        elif budget.remaining_candidates() <= 0:
            report["repair_stop_reason"] = "candidate_budget"
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


def _repair_one_elite(pool: EliteRepairPool, *, elite: Dict[str, Any], elite_index: int, state: Any,
                      evaluate: Callable[..., Dict[str, Any]], budget: Any, repair_deadline: float,
                      clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                      improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool,
                      before_decode: Callable[[], None], seen_decisions: set,
                      improved_elites: List[Dict[str, Any]]) -> Iterator[None]:
    """Visit one elite's neighbours; yields after every evaluated neighbour so the rotation can interleave."""
    report = pool.report
    pruning = report["repair_pruning_report"]
    neighborhood = elite["neighborhood"]
    generated = 0
    offset = elite.get("decision_offset", 0)
    for kind, decision, variant_profile in islice(neighborhood.profiled_decisions(), offset, None):
        if (generated >= pool.limits.max_neighbors_per_elite
                or budget.remaining_candidates() <= 0
                or clock() >= repair_deadline):
            break
        generated += 1
        elite["decision_offset"] = offset + generated
        pruning["generated_candidates"] += 1
        decision_identity = (variant_profile.feature_basis, decision)
        if decision_identity in seen_decisions:
            _prune_duplicate(pruning, kind=kind, elite_index=elite_index)
            continue
        seen_decisions.add(decision_identity)
        profile = replace(variant_profile, slug="v2_repair_" + kind, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                          candidate_policy="elite_repair")
        candidate = _evaluate_neighbor(evaluate, decision=decision, profile=profile, strict_mode=strict_mode,
                                       attempts=attempts, report_state=report_state, pruning=pruning,
                                       parent=elite["candidate"], before_decode=before_decode)
        if candidate is not None:
            append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile)
            event = _acceptance_event(pool, candidate=candidate, elite=elite, best=state.best, report_state=report_state)
            if event is not None:
                if report_state is not None:
                    report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN, acceptance_event=event)
                append_graph_trace(improvement_trace=improvement_trace, candidate=candidate, profile=profile, clock=clock, t_begin=t_begin)
                report["repair_accepted"] = True
                report["repair_best_origin"] = GRAPH_READY_V2_REPAIRED_ORIGIN
                state.best = candidate
                improved_elites.append({"candidate": candidate, "profile": profile,
                                        "basis_profiles": tuple(item[0] for item in neighborhood.variants)})
        yield


def _evaluate_neighbor(evaluate: Callable[..., Dict[str, Any]], *, decision: RepairDecision, profile: GraphReadyWeightProfile,
                       strict_mode: bool, attempts: List[Dict[str, Any]], report_state: Any,
                       pruning: Dict[str, Any], parent: Dict[str, Any], before_decode: Callable[[], None]) -> Optional[Dict[str, Any]]:
    try:
        order = list(decision.batch_order)
        return evaluate(profile=profile, order=order, repair_order=order, repair_decision=decision, before_decode=before_decode)
    except _RepairBudgetExhausted:
        pruning["pruned_candidates"] += 1
        counts = pruning["pruned_by_rule"]
        counts["budget_before_decode"] = counts.get("budget_before_decode", 0) + 1
        return None
    except ValidationError as exc:
        if strict_mode or is_graph_ready_v2_contract_error(exc) or exc.field == "graph_ready_elite_repair":
            raise
        reason = reason_from_validation(exc)
        _reject(pruning, reason, report_state)
        record_rejected_attempt(attempts=attempts, strategy=parent["strategy"], dispatch_rule=parent["dispatch_rule"], reason=reason,
                                message=str(exc), profile_slug=profile.slug)
        return None


def _acceptance_event(pool: EliteRepairPool, *, candidate: Dict[str, Any], elite: Dict[str, Any],
                      best: Optional[Dict[str, Any]], report_state: Any) -> Optional[Dict[str, Any]]:
    pruning = pool.report["repair_pruning_report"]
    fingerprint = pool.fingerprint(candidate, elite["fingerprint"].output_fingerprint)
    pool.seen_outputs.add(fingerprint.output_fingerprint)
    state_fingerprint = None
    if report_state is not None:
        state_fingerprint = report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN)
    if fingerprint.same_as_parent or fingerprint.same_as_seen:
        pruning["same_fingerprint_rejected"] += 1
        pruning["duplicate_output_rejected"] += 1
        already_recorded = state_fingerprint is not None and (state_fingerprint.same_as_parent or state_fingerprint.same_as_seen)
        _reject(pruning, "same_fingerprint", None if already_recorded else report_state)
        return None
    if candidate["summary"].failed_ops or not candidate["summary"].success:
        _reject(pruning, "repair_infeasible", report_state)
        return None
    event = build_graph_ready_improve_only_acceptance_event(
        candidate_score=candidate["score"], incumbent_score=(best or {}).get("score"), seed=pool.seed)
    if event is None:
        _reject(pruning, "no_strict_improvement", report_state)
        return None
    if not candidate_is_preferred(candidate=candidate, incumbent=best, candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
                                  incumbent_origin=str((best or {}).get("candidate_origin") or "baseline"),
                                  candidate_fingerprint=fingerprint,
                                  incumbent_fingerprint_changed=bool(report_state and report_state.best_fingerprint_changed())):
        _reject(pruning, "acceptance_rejected", report_state)
        return None
    return event


def _prune_duplicate(pruning: Dict[str, Any], *, kind: str, elite_index: int) -> None:
    pruning["pruned_candidates"] += 1
    pruning["duplicate_decision_pruned"] += 1
    counts = pruning["pruned_by_rule"]
    counts["duplicate_decision"] = counts.get("duplicate_decision", 0) + 1
    pruning["rule_trace"].append({"rule": "duplicate_decision", "generator": kind, "elite_index": elite_index})


def _reject(pruning: Dict[str, Any], reason: str, report_state: Any) -> None:
    pruning["rejected_candidates"] += 1
    reasons = pruning["rejected_by_reason"]
    reasons[reason] = reasons.get(reason, 0) + 1
    if report_state is not None:
        report_state.mark_candidate_rejected(reason=reason)


def _repair_status(report: Dict[str, Any]) -> str:
    pruning = report["repair_pruning_report"]
    if report["repair_accepted"]:
        return "strict_improvement"
    if not pruning["evaluated_candidates"]:
        exhausted = pruning["skipped_by_budget"] or report["repair_stop_reason"] in {"time_budget", "candidate_budget"}
        return "skipped_by_budget" if exhausted else "no_strict_improvement"
    if pruning["rejected_candidates"] == pruning["evaluated_candidates"] and not pruning["rejected_by_reason"].get("no_strict_improvement"):
        return "all_candidates_rejected"
    return "no_strict_improvement"


def _publish_report(report: Dict[str, Any], *, report_state: Any, attempts: List[Dict[str, Any]]) -> None:
    # Existing public projection keeps profile.message; raw attempts remain diagnostics-only.
    attempts.append({"tag": REPAIR_PHASE, "candidate_status": "phase_summary", "elite_repair": report})
    if report_state is None:
        return
    graph = dict((report_state.candidate_profile or {}).get("graph_ready_optimization") or {})
    graph["elite_repair"] = report
    message = str((report_state.candidate_profile or {}).get("message") or "")
    report_state.update_candidate_profile(graph_ready_optimization=graph, message=(message + " " + repair_public_message(report)).strip())
    if report["repair_status"].startswith("skipped") or report["repair_status"] == "not_run":
        report_state.mark_phase_skipped(REPAIR_PHASE, report["repair_status"])
