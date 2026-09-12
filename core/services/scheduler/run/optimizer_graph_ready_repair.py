from __future__ import annotations

from dataclasses import replace
from itertools import islice
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_candidate_comparison import candidate_is_preferred
from .optimizer_candidate_fingerprint import build_candidate_fingerprint
from .optimizer_graph_ready_acceptance import build_graph_ready_improve_only_acceptance_event
from .optimizer_graph_ready_context import reason_from_validation
from .optimizer_graph_ready_feature_basis import select_profile_metrics
from .optimizer_graph_ready_profiles import GRAPH_READY_V2_REPAIRED_ORIGIN, GraphReadyWeightProfile
from .optimizer_graph_ready_repair_contract import (
    REPAIR_PHASE,
    EliteRepairLimits,
    finish_repair_report,
    new_repair_report,
)
from .optimizer_graph_ready_repair_decisions import RepairDecision
from .optimizer_graph_ready_repair_portfolio import ParentRepairPortfolio, RepairPortfolio, build_repair_portfolio
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


def run_graph_ready_elite_repair(
    pool: EliteRepairPool, *, best: Optional[Dict[str, Any]], evaluate: Callable[..., Dict[str, Any]],
    profile_evaluations: int, deadline: float, clock: Callable[[], float], t_begin: float,
    attempts: List[Dict[str, Any]], improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool,
) -> Optional[Dict[str, Any]]:
    report = pool.report
    pruning = report["repair_pruning_report"]
    started = clock()
    remaining_ms = max(int((deadline - started) * 1000), 0)
    budget_ms = remaining_ms if pool.limits.time_budget_ms is None else min(remaining_ms, pool.limits.time_budget_ms)
    repair_deadline = min(deadline, started + budget_ms / 1000.0)
    report["repair_time_budget_ms"] = pruning["budget_ms"] = budget_ms
    report["repair_candidate_budget"] = max(pool.limits.max_candidates - profile_evaluations, 0)
    report["selected_elites"] = len(pool.elites)
    pruning["candidate_space_total"] = sum(elite["neighborhood"].candidate_count for elite in pool.elites)
    pruning["skipped_by_budget"] = report["skipped_neighbors_by_top_k"]
    report["repair_best_origin"] = (best or {}).get("candidate_origin")
    if not pool.limits.enabled:
        report["repair_status"] = "not_run"
    elif not pool.elites:
        report["repair_status"] = "skipped_by_budget" if report["repair_stop_reason"] == "time_budget" else "skipped_no_elite"
    else:
        best = _repair_elites(pool, best=best, evaluate=evaluate, repair_deadline=repair_deadline, clock=clock,
                              t_begin=t_begin, attempts=attempts, improvement_trace=improvement_trace,
                              report_state=report_state, strict_mode=strict_mode)
        report["repair_status"] = _repair_status(report)
    finished = clock()
    pruning["runtime_ms"] = max(int((finished - started) * 1000), 0)
    report["deadline_overrun_ms"] = max(int((finished - repair_deadline) * 1000), 0)
    finish_repair_report(report)
    _publish_report(report, report_state=report_state, attempts=attempts)
    if report_state is not None and finished >= deadline:
        report_state.mark_deadline_reached()
    return best


def _repair_elites(pool: EliteRepairPool, *, best: Optional[Dict[str, Any]], evaluate: Callable[..., Dict[str, Any]],
                   repair_deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                   improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool) -> Optional[Dict[str, Any]]:
    report = pool.report
    pruning = report["repair_pruning_report"]
    # Include operation priorities and resource choices, not only batch order.
    seen_decisions: set = set()

    def before_decode() -> None:
        if clock() >= repair_deadline or pruning["evaluated_candidates"] >= report["repair_candidate_budget"]:
            raise _RepairBudgetExhausted()
        pruning["evaluated_candidates"] += 1

    elites = list(pool.elites)
    queued_elites: List[Dict[str, Any]] = []
    for round_index in range(pool.limits.max_rounds):
        improved_elites: List[Dict[str, Any]] = []
        deferred_elites: List[Dict[str, Any]] = []
        for elite_index, elite in enumerate(elites):
            best = _repair_one_elite(
                pool, elite=elite, elite_index=elite_index, best=best, evaluate=evaluate,
                repair_deadline=repair_deadline, clock=clock, t_begin=t_begin, attempts=attempts,
                improvement_trace=improvement_trace, report_state=report_state, strict_mode=strict_mode,
                before_decode=before_decode, seen_decisions=seen_decisions, improved_elites=improved_elites)
            if _defer_to_improved_elites(pool, elites, elite_index, round_index, improved_elites):
                _retain_pending_tail(elite, pruning, deferred_elites)
                deferred_elites.extend(elites[elite_index + 1:])
                for deferred in deferred_elites:
                    deferred["pending_tail"] = True
                break
            _retain_pending_tail(elite, pruning, deferred_elites)
        deferred_elites.extend(queued_elites)
        # Give retained parents their first visit before resuming another tail;
        # sharing basis variants must not consume all slots on the first parent.
        deferred_elites.sort(key=lambda elite: bool(elite.get("decision_offset", 0)))
        report["repair_rounds_completed"] = round_index + 1
        report["repair_round_improvements"].append(len(improved_elites))
        if clock() >= repair_deadline:
            report["repair_stop_reason"] = "time_budget"
        elif pruning["evaluated_candidates"] >= report["repair_candidate_budget"]:
            report["repair_stop_reason"] = "candidate_budget"
        elif not improved_elites and not deferred_elites:
            report["repair_stop_reason"] = "no_improvement"
        elif round_index + 1 >= pool.limits.max_rounds:
            report["repair_stop_reason"] = "max_rounds"
        else:
            next_round = _prepare_next_repair_round(
                pool, improved_elites=improved_elites, deferred_elites=deferred_elites,
                repair_deadline=repair_deadline, clock=clock)
            if next_round is None:
                _skip_deferred_by_budget(pruning, deferred_elites)
                report["repair_stop_reason"] = "time_budget"
                break
            elites, queued_elites = next_round
            continue
        _skip_deferred_by_budget(pruning, deferred_elites)
        break
    return best


def _prepare_next_repair_round(
    pool: EliteRepairPool, *, improved_elites: List[Dict[str, Any]], deferred_elites: List[Dict[str, Any]],
    repair_deadline: float, clock: Callable[[], float],
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    next_elites: List[Dict[str, Any]] = []
    next_slots = max(pool.limits.top_k - len(deferred_elites), 1)
    for improved in sorted(improved_elites, key=lambda elite: tuple(elite["candidate"]["score"]))[:next_slots]:
        if clock() >= repair_deadline:
            break
        elite = pool.make_elite(improved["candidate"], improved["profile"])
        for profile in improved.get("basis_profiles", ()):
            if clock() >= repair_deadline:
                break
            pool.add_basis_variant(elite, profile)
        next_elites.append(elite)
    if not next_elites and improved_elites:
        return None
    pool.report["repair_pruning_report"]["candidate_space_total"] += sum(
        elite["neighborhood"].candidate_count for elite in next_elites)
    next_elites.extend(deferred_elites)
    # Pending tails keep their place without increasing this round's
    # active top-k set. A quiet round may still service this queue.
    return next_elites[:pool.limits.top_k], next_elites[pool.limits.top_k:]


def _skip_deferred_by_budget(pruning: Dict[str, Any], deferred_elites: List[Dict[str, Any]]) -> None:
    # Deferral alone consumes no budget; count these only when search really stops.
    pruning["skipped_by_budget"] += sum(_pending_neighbors(elite) for elite in deferred_elites)


def _pending_neighbors(elite: Dict[str, Any]) -> int:
    return elite["neighborhood"].candidate_count - elite.get("decision_offset", 0)


def _retain_pending_tail(elite: Dict[str, Any], pruning: Dict[str, Any], deferred_elites: List[Dict[str, Any]]) -> None:
    pending = _pending_neighbors(elite)
    if pending:
        elite["pending_tail"] = True
        deferred_elites.append(elite)
        # A queued tail has a later opportunity; count it only at real termination.
        pruning["skipped_by_budget"] -= pending


def _defer_to_improved_elites(pool: EliteRepairPool, elites: List[Dict[str, Any]], elite_index: int,
                             round_index: int, improved_elites: List[Dict[str, Any]]) -> bool:
    if not improved_elites or round_index + 1 >= pool.limits.max_rounds:
        return False
    # Spend the next round on a measured improvement before revisiting older
    # elites, including the current elite's unconsumed tail.
    pool.report["repair_deferred_by_improvement"] += sum(
        _pending_neighbors(elite) for elite in elites[elite_index:])
    return True


def _repair_one_elite(pool: EliteRepairPool, *, elite: Dict[str, Any], elite_index: int,
                      best: Optional[Dict[str, Any]], evaluate: Callable[..., Dict[str, Any]],
                      repair_deadline: float, clock: Callable[[], float], t_begin: float,
                      attempts: List[Dict[str, Any]], improvement_trace: List[Dict[str, Any]],
                      report_state: Any, strict_mode: bool, before_decode: Callable[[], None],
                      seen_decisions: set, improved_elites: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    report = pool.report
    pruning = report["repair_pruning_report"]
    neighborhood = elite["neighborhood"]
    generated = 0
    offset = elite.get("decision_offset", 0)
    for kind, decision, variant_profile in islice(neighborhood.profiled_decisions(), offset, None):
        if (generated >= pool.limits.max_neighbors_per_elite
                or pruning["evaluated_candidates"] >= report["repair_candidate_budget"]
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
        if candidate is None:
            continue
        append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile)
        event = _acceptance_event(pool, candidate=candidate, elite=elite, best=best, report_state=report_state)
        if event is None:
            continue
        if report_state is not None:
            report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN, acceptance_event=event)
        append_graph_trace(improvement_trace=improvement_trace, candidate=candidate, profile=profile, clock=clock, t_begin=t_begin)
        report["repair_accepted"] = True
        report["repair_best_origin"] = GRAPH_READY_V2_REPAIRED_ORIGIN
        best = candidate
        improved_elites.append({"candidate": candidate, "profile": profile,
                                "basis_profiles": tuple(item[0] for item in neighborhood.variants)})
    pruning["skipped_by_budget"] += _pending_neighbors(elite)
    return best


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
