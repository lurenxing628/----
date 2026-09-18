"""Iterated greedy over the decoded operation order of the incumbent graph candidate.

Each iteration destroys part of the reference order with one of three OR-Tools-style neighbourhoods
(time window, resource window, tardy/random; successful-generator continuation, adaptive size), parks the removed
operations at their latest feasible rank and re-inserts them one at a time at the best of a bounded
set of topologically valid ranks, judged by the formal SGS decode. Trial decodes resume from the
reference decode's checkpoints; the iteration's final order is decoded in full again and must
reproduce the resumed trial bit for bit (fail-loud otherwise). The walk accepts by simulated annealing
with exponential cooling and restarts from a small solution pool after stagnation. Every complete
decode is also an improve-only candidate for the incumbent. The stage spends only what it is given:
wall clock up to its deadline and its own decode cap; a decode expected to overrun is never started.

The parent order is the parent's decoded start-time operation order with its explicit resource overrides
(``_parent_from_candidate``); re-decoding it under the IG context may reproduce the parent or drift, and that
drift is search freedom (2026-09-18: pick-sequence identities and pinned resources measured worse). Reference
captures are accounted as captures (reproduced or divergent), not as rejected or improving search decodes.
"""
from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple
from typing import OrderedDict as OrderedDictType

from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpoint, decode_output_digest
from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_context import reason_from_validation
from .optimizer_graph_ready_decode_capture import capture_failure_reason, is_capture_failure
from .optimizer_graph_ready_iterated_greedy_acceptance import (
    ExponentialCooling,
    PoolEntry,
    SolutionPool,
    TemperatureScale,
    profile_identity,
    sa_accept,
)
from .optimizer_graph_ready_iterated_greedy_checkpoints import CheckpointStore
from .optimizer_graph_ready_iterated_greedy_contract import (
    IG_CANDIDATE_POLICY,
    IG_PHASE,
    IG_PROFILE_SLUG,
    IteratedGreedyLimits,
    _BudgetExhausted,
    ig_decode_profile,
    iterated_greedy_public_message,
    new_iterated_greedy_report,
)
from .optimizer_graph_ready_iterated_greedy_features import entry_features, tardy_signals
from .optimizer_graph_ready_iterated_greedy_incumbent import IGIncumbentTracker
from .optimizer_graph_ready_iterated_greedy_incumbent import feasible_candidate as _feasible
from .optimizer_graph_ready_iterated_greedy_iteration import IGIteration
from .optimizer_graph_ready_iterated_greedy_moves import (
    _insertion_positions,
    _latest_rank,
    _Parent,
    _parent_from_candidate,
    _park,
)
from .optimizer_graph_ready_iterated_greedy_neighborhoods import (
    GeneratorRotation,
    build_generators,
    tardy_random_destroy,
)
from .optimizer_graph_ready_iterated_greedy_reference import (
    activate_entry,
    adopt_incumbent,
    reference_for_iteration,
    seed_solution_pool,
)
from .optimizer_graph_ready_iterated_greedy_start import start_reference
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile
from .optimizer_graph_ready_repair_decisions import RepairDecision
from .optimizer_graph_ready_reporting import append_graph_attempt, record_rejected_attempt
from .optimizer_graph_ready_v2_contract import is_graph_ready_v2_contract_error

# Decoded candidates kept for feature extraction; older ones are dropped (memory bound).
_CANDIDATE_CACHE_SIZE = 32
_STOP_BY_BUDGET = ("time_budget", "decode_budget", "decode_would_overrun")
_FAILED = ((), False)
# Helpers reachable through this module for existing callers and tests.
_destroy = tardy_random_destroy
__all__ = ["IG_CANDIDATE_POLICY", "IG_PROFILE_SLUG", "_IteratedGreedySearch", "_BudgetExhausted", "_Parent", "_destroy",
           "_insertion_positions", "_latest_rank", "_park", "_parent_from_candidate", "_publish", "_stage_deadline",
           "admit_parent_decode"]


def _stage_deadline(limits: IteratedGreedyLimits, *, started: float, deadline: float) -> float:
    if limits.time_budget_ms is None:
        return deadline
    return min(deadline, started + limits.time_budget_ms / 1000.0)


def admit_parent_decode(best: Dict[str, Any], *, clock: Callable[[], float], deadline: float, report: Dict[str, Any]) -> None:
    """Do not start the reference capture when the parent's own decode cost does not fit the remaining time."""
    now = clock()
    if now >= deadline:
        raise _BudgetExhausted("time_budget")
    parent_cost = float(best.get("runtime_ms") or 0) / 1000.0
    if parent_cost and now + parent_cost > deadline:
        report["decode_admission"] = {"policy": "observed_parent_candidate_runtime", "estimated_decode_ms": parent_cost * 1000.0,
                                      "remaining_ms": max(deadline - now, 0.0) * 1000.0}
        raise _BudgetExhausted("decode_would_overrun")


class _IteratedGreedySearch:
    def __init__(self, *, limits: IteratedGreedyLimits, parent: _Parent, profile: GraphReadyWeightProfile, pool: Any,
                 evaluate: Callable[..., Dict[str, Any]], metrics_by_op_id: Dict[int, Dict[str, Any]], start_dt: Any,
                 seed: int, deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                 improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool, report: Dict[str, Any],
                 operations: Optional[List[Any]] = None, graph_context: Optional[Dict[str, Any]] = None) -> None:
        self.limits = limits
        self.parent = parent
        self.operations = operations
        self.graph_context = graph_context
        self.profile = ig_decode_profile(profile)
        self.pool = pool
        self.evaluate = evaluate
        self.metrics = metrics_by_op_id
        self.start_dt = start_dt
        self.seed = int(seed)
        self.deadline = deadline
        self.clock = clock
        self.t_begin = t_begin
        self.attempts = attempts
        self.improvement_trace = improvement_trace
        self.report_state = report_state
        self.strict_mode = strict_mode
        self.report = report
        self.rnd = random.Random(self.seed * 7919 + 17)
        # Pool sampling must not change the destroy/reinsert random stream.
        self.pool_rnd = random.Random("graph-ready-ig-pool:" + str(self.seed))
        self.generators = build_generators(limits.generators, initial_size=limits.destruction_size,
                                           max_size=limits.max_destruction_size)
        self.rotation = GeneratorRotation(self.generators)
        self.checkpoints = CheckpointStore(limits.checkpoint_count)
        self.cooling = ExponentialCooling(limits.temperature_ratio_start, limits.temperature_ratio_end)
        self.scale = TemperatureScale()
        self.solution_pool = SolutionPool(limits.pool_size)
        self.scores: Dict[Tuple[int, ...], Tuple[Tuple[float, ...], bool]] = {}
        # Output digests of resumed trial decodes, consumed by the full decode of the same order.
        self.digests: Dict[Tuple[int, ...], Tuple[str, Tuple[float, ...]]] = {}
        self.scored_decodes = 0
        # Annotate with typing.OrderedDict: subscripting collections.OrderedDict needs Python 3.9 (PEP 585).
        self.candidates: OrderedDictType[Tuple[int, ...], Dict[str, Any]] = OrderedDict()
        self.decoded_entries: OrderedDictType[Tuple[int, ...], PoolEntry] = OrderedDict()
        self.decode_seconds: List[float] = []
        self.incumbent = IGIncumbentTracker(pool=pool, report_state=report_state, report=report, seed=seed,
                                             clock=clock, t_begin=t_begin, improvement_trace=improvement_trace)
        self.reference: Optional[PoolEntry] = None
        # The known solution a running full decode only re-captures under this context (None for search decodes).
        self.capturing: Optional[Dict[str, Any]] = None
        self.non_improving = 0
        self.idle_iterations = 0
        self.rejected_iterations = 0
        self.improved_incumbent = False
        self.started = clock()
        report["time_budget_ms"] = max(int((deadline - self.started) * 1000), 0)

    @property
    def best(self) -> Optional[Dict[str, Any]]:
        return self.incumbent.best

    @best.setter
    def best(self, candidate: Optional[Dict[str, Any]]) -> None:
        self.incumbent.best = candidate

    def _require_best(self) -> Dict[str, Any]:
        """run()/adopt_incumbent() install the incumbent before any pool seeding or decode."""
        best = self.best
        if best is None:
            raise RuntimeError("Iterated greedy has no incumbent candidate.")
        return best

    # ---- driver -------------------------------------------------------------------------------------------------------
    def run(self, best: Dict[str, Any]) -> Dict[str, Any]:
        self.best = best
        report = self.report
        try:
            admit_parent_decode(best, clock=self.clock, deadline=self.deadline, report=report)
        except _BudgetExhausted as exc:
            report["status"], report["stop_reason"] = "skipped_by_budget", exc.reason
            return best
        try:
            self._start_reference()
            for _iteration in range(self.limits.max_iterations):
                self.iterate_once()
            else:
                report["stop_reason"] = "max_iterations"
        except _BudgetExhausted as exc:
            report["stop_reason"] = exc.reason
        self._finish_report()
        return self.best

    def _start_reference(self) -> None:
        """Choose an existing quality tier and formally check an optional constructive start."""
        start_reference(self)

    def adopt_incumbent(self, candidate: Dict[str, Any], profile: Optional[GraphReadyWeightProfile] = None) -> None:
        """Another stage improved the incumbent: base the walk on it, as OR-Tools LNS bases on the shared best."""
        adopt_incumbent(self, candidate, profile)

    def _set_parent(self, parent: _Parent, profile: GraphReadyWeightProfile, *, count_switch: bool = True) -> None:
        effective = ig_decode_profile(profile)
        before = (self.parent.batch_order, self.parent.inherited, profile_identity(self.profile))
        after = (parent.batch_order, parent.inherited, profile_identity(effective))
        self.parent, self.profile = parent, effective
        if before != after:
            self.scores.clear()
            self.digests.clear()
            self.candidates.clear()
            self.decoded_entries.clear()
            if count_switch:
                self.report["context_switches"] += 1

    def _activate_entry(self, entry: PoolEntry) -> None:
        activate_entry(self, entry)

    def _seed_solution_pool(self) -> None:
        seed_solution_pool(self)

    def iterate_once(self) -> None:
        """One-shot driver; the shared stage uses the same iteration's resumable steps."""
        iteration = IGIteration(self)
        while iteration.step():
            pass

    def _reference_for_iteration(self) -> PoolEntry:
        return reference_for_iteration(self)

    def _accept_walk(self, entry: PoolEntry, reference: PoolEntry) -> None:
        report = self.report
        self.scale.observe(entry.score, reference.score)
        self.solution_pool.refresh(entry)
        if entry.score <= reference.score:
            accepted = True
        else:
            progress = (self.clock() - self.started) / max(self.deadline - self.started, 1e-9)
            temperature = self.cooling.temperature(self.scale.value, progress)
            secondary = self.cooling.temperature(self.scale.secondary, progress)
            accepted = sa_accept(entry.score, reference.score, temperature=temperature, u=self.rnd.random(),
                                 secondary_temperature=secondary)
        if not accepted:
            report["acceptance"]["rejected"] += 1
            return
        report["walk_accepted"] += 1
        report["walk_improved"] += int(entry.score < reference.score)
        report["walk_accepted_worse"] += int(entry.score > reference.score)
        self.reference = entry

    def _require_budget(self) -> None:
        now = self.clock()
        if now >= self.deadline:
            raise _BudgetExhausted("time_budget")
        if self.report["decodes"] >= self.limits.max_decodes:
            raise _BudgetExhausted("decode_budget")
        if self.decode_seconds and now + sum(self.decode_seconds) / len(self.decode_seconds) > self.deadline:
            raise _BudgetExhausted("decode_would_overrun")

    def _features(self, entry: PoolEntry) -> Dict[str, Any]:
        return entry_features(self, entry)

    def _signals(self, candidate: Dict[str, Any]) -> Dict[int, float]:
        return tardy_signals(self, candidate)

    # ---- decoding and incumbent acceptance ----------------------------------------------------------------------------
    def _score_trial(self, order: Tuple[int, ...], reference: PoolEntry) -> Optional[Tuple[Tuple[float, ...], bool]]:
        known = self.scores.get(order)
        if known is not None:
            self.report["duplicate_decision_pruned"] += 1
            return None if known is _FAILED else known
        resume = self.checkpoints.best_for(reference.checkpoints, base_order=reference.order, trial_order=order)
        candidate = self._decode(order, resume=resume)
        if candidate is None:
            # A rejected decision is not retried; the rejection reason is already recorded.
            self.scores[order] = _FAILED
            return None
        scored = (tuple(candidate["score"]), _feasible(candidate))
        self.scores[order] = scored
        self.scored_decodes += 1
        self._remember(order, candidate)
        if resume is not None:
            self.digests[order] = (decode_output_digest(candidate["results"], candidate["summary"]), tuple(candidate["score"]))
            if _feasible(candidate) and (self.best is None or tuple(candidate["score"]) < tuple(self.best["score"])):
                self.report["validation_decodes"] += 1
                verified = self._decode_entry(order)
                if verified is None:
                    return None
                return verified.score, True
        return scored

    def _decode_entry(self, order: Tuple[int, ...]) -> Optional[PoolEntry]:
        """Full decode with checkpoints; must reproduce an earlier resumed decode of the same order."""
        if self.scores.get(order) is _FAILED:
            self.report["duplicate_decision_pruned"] += 1
            return None
        known = self.decoded_entries.get(order)
        if known is not None:
            self.decoded_entries.move_to_end(order)
            self.report["duplicate_decision_pruned"] += 1
            return known
        recapture = order in self.scores and order not in self.digests
        request, captured = self.checkpoints.request_for(len(order))
        candidate = self._decode(order, checkpoints=request)
        if candidate is None:
            if order in self.digests:
                self._equivalence_violation()
            self.scores[order] = _FAILED
            return None
        # A full trial may need one new decode to capture a future reference's checkpoints.
        self.report["reference_capture_decodes"] += int(recapture)
        feasible = _feasible(candidate)
        score = tuple(candidate["score"])
        self.scores[order] = (score, feasible)
        self.scored_decodes += 1
        self._remember(order, candidate)
        if not feasible:
            return None
        # A capture refused mid-decode disables checkpoints; its partial snapshots are not a resumable set.
        entry = PoolEntry(order=order, score=score, candidate=candidate, decoded_order=True,
                          checkpoints=captured if self.checkpoints.enabled else [],
                          batch_order=self.parent.batch_order, resource_overrides=self.parent.inherited, profile=self.profile)
        self.decoded_entries[order] = entry
        while len(self.decoded_entries) > self.solution_pool.size:
            self.decoded_entries.popitem(last=False)
        return entry

    @staticmethod
    def _equivalence_violation() -> None:
        raise ValidationError("GraphReady 迭代贪心的断点续排结果与全量解码不一致，系统已停止排产。",
                              field="graph_ready_iterated_greedy",
                              details={"reason": "decode_checkpoint_equivalence_violation"})

    def _remember(self, order: Tuple[int, ...], candidate: Dict[str, Any]) -> None:
        self.candidates[order] = candidate
        self.candidates.move_to_end(order)
        while len(self.candidates) > _CANDIDATE_CACHE_SIZE:
            self.candidates.popitem(last=False)

    def _decode(self, order: Tuple[int, ...], *, resume: Optional[DecodeCheckpoint] = None,
                checkpoints: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        decision = RepairDecision(self.parent.batch_order, order, self.parent.inherited)
        batch_order = list(decision.batch_order)
        decode_kwargs: Dict[str, Any] = {}
        if resume is not None:
            decode_kwargs["decode_resume"] = resume
        if checkpoints is not None:
            decode_kwargs["decode_checkpoints"] = checkpoints
        decode_started = self.clock()
        try:
            candidate = self.evaluate(profile=self.profile, order=batch_order, repair_order=batch_order,
                                      repair_decision=decision, before_decode=self._before_decode, **decode_kwargs)
        except ValidationError as exc:
            if checkpoints is not None and is_capture_failure(exc, resumed=resume is not None):
                # Capture refused or lost before the decode finished: degrade to plain full decodes, report why.
                self.report["checkpoint_capture_rejections"] += 1
                self.report["decodes"] -= 1  # The retry below counts the same logical decode once.
                self.checkpoints.disable(capture_failure_reason(exc))
                return self._decode(order)
            if self.strict_mode or is_graph_ready_v2_contract_error(exc) or exc.field in (
                    "graph_ready_elite_repair", "graph_ready_iterated_greedy", "decode_checkpoint"):
                raise
            reason = reason_from_validation(exc)
            self._reject(reason)
            best = self._require_best()
            record_rejected_attempt(attempts=self.attempts, strategy=best["strategy"], dispatch_rule=best["dispatch_rule"],
                                    reason=reason, message=str(exc), profile_slug=self.profile.slug)
            return None
        self.decode_seconds.append(max(self.clock() - decode_started, 0.0))
        self.report["mean_decode_ms"] = sum(self.decode_seconds) * 1000.0 / len(self.decode_seconds)
        self.checkpoints.note_decode(len(order), resumed_from=resume)
        append_graph_attempt(attempts=self.attempts, candidate=candidate, profile=self.profile)
        if resume is not None:
            self.incumbent.observe_trial(candidate)
        else:
            expected = self.digests.pop(order, None)
            if expected is not None:
                self.checkpoints.equivalence_checks += 1
                actual = (decode_output_digest(candidate["results"], candidate["summary"]), tuple(candidate["score"]))
                if actual != expected:
                    self._equivalence_violation()
            self._consider_for_incumbent(candidate)
        return candidate

    def _before_decode(self) -> None:
        try:
            self._require_budget()
        except _BudgetExhausted:
            self.report["budget_pruned_before_decode"] += 1
            raise
        self.report["decodes"] += 1

    def _consider_for_incumbent(self, candidate: Dict[str, Any]) -> None:
        improved = self.incumbent.consider(candidate, profile=self.profile, capture_of=self.capturing)
        self.improved_incumbent = improved or self.improved_incumbent

    def _reject(self, reason: str, *, record: bool = True) -> None:
        self.incumbent.reject(reason, record=record)

    def _finish_report(self) -> None:
        report = self.report
        report["status"] = "strict_improvement" if report["accepted"] else "no_strict_improvement"
        if not report["decodes"] and report["stop_reason"] in _STOP_BY_BUDGET:
            report["status"] = "skipped_by_budget"
        report["generators"] = {generator.name: generator.summary() for generator in self.generators}
        report["checkpoints"] = self.checkpoints.summary()
        report["acceptance"]["temperature_scale"] = self.scale.value if self.scale.count else None
        report["acceptance"]["secondary_temperature_scale"] = self.scale.secondary if self.scale.secondary_count else None
        report["pool"]["entries"] = len(self.solution_pool.entries)


def _publish(report: Dict[str, Any], *, report_state: Any, attempts: List[Dict[str, Any]]) -> None:
    attempts.append({"tag": IG_PHASE, "candidate_status": "phase_summary", "iterated_greedy": report})
    if report_state is None:
        return
    graph = dict((report_state.candidate_profile or {}).get("graph_ready_optimization") or {})
    graph["iterated_greedy"] = report
    message = str((report_state.candidate_profile or {}).get("message") or "")
    report_state.update_candidate_profile(graph_ready_optimization=graph,
                                          message=(message + " " + iterated_greedy_public_message(report)).strip())
    if report["status"].startswith("skipped") or report["status"] == "not_run":
        report_state.mark_phase_skipped(IG_PHASE, report["status"])
