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
    IG_PHASE,
    IteratedGreedyLimits,
    _BudgetExhausted,
    iterated_greedy_public_message,
    new_iterated_greedy_report,
)
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
from .optimizer_graph_ready_iterated_greedy_start import start_reference
from .optimizer_graph_ready_profiles import GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, GraphReadyWeightProfile
from .optimizer_graph_ready_repair_decisions import RepairDecision
from .optimizer_graph_ready_reporting import append_graph_attempt, record_rejected_attempt
from .optimizer_graph_ready_v2_contract import is_graph_ready_v2_contract_error

IG_PROFILE_SLUG = "v2_ig_destroy_repair"
IG_CANDIDATE_POLICY = "iterated_greedy"
# Decoded candidates kept for feature extraction; older ones are dropped (memory bound).
_CANDIDATE_CACHE_SIZE = 32
_STOP_BY_BUDGET = ("time_budget", "decode_budget", "decode_would_overrun")
_FAILED = ((), False)
# Helpers reachable through this module for existing callers and tests.
_destroy = tardy_random_destroy
__all__ = ["_IteratedGreedySearch", "_BudgetExhausted", "_Parent", "_destroy", "_insertion_positions", "_latest_rank",
           "_park", "_parent_from_candidate", "_publish", "_stage_deadline"]


def _stage_deadline(limits: IteratedGreedyLimits, *, started: float, deadline: float) -> float:
    if limits.time_budget_ms is None:
        return deadline
    return min(deadline, started + limits.time_budget_ms / 1000.0)


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
        self.profile = replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                               candidate_policy=IG_CANDIDATE_POLICY)
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
        parent_cost = float(best.get("runtime_ms") or 0) / 1000.0
        if self.clock() >= self.deadline or (parent_cost and self.clock() + parent_cost > self.deadline):
            report["status"], report["stop_reason"] = "skipped_by_budget", "time_budget"
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
        self.best = candidate
        if self.operations is None or self.graph_context is None:
            return
        parent = _parent_from_candidate(candidate, operations=self.operations, graph_context=self.graph_context)
        if parent is None:
            return
        self.report["incumbent_adoptions"] += 1
        self._set_parent(parent, profile or self.profile)
        self._require_budget()
        entry = self._decode_entry(parent.order)
        if entry is not None:
            self.solution_pool.refresh(entry)
            self.reference = entry
            self.non_improving = 0

    def _set_parent(self, parent: _Parent, profile: GraphReadyWeightProfile) -> None:
        effective = replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                            candidate_policy=IG_CANDIDATE_POLICY)
        before = (self.parent.batch_order, self.parent.inherited, profile_identity(self.profile))
        after = (parent.batch_order, parent.inherited, profile_identity(effective))
        self.parent, self.profile = parent, effective
        if before != after:
            self.scores.clear()
            self.digests.clear()
            self.candidates.clear()
            self.decoded_entries.clear()
            self.report["context_switches"] += 1

    def _activate_entry(self, entry: PoolEntry) -> None:
        self._set_parent(replace(self.parent, order=entry.order, batch_order=entry.batch_order,
                                 inherited=entry.resource_overrides), entry.profile or self.profile)

    def _seed_solution_pool(self) -> None:
        if self.operations is None or self.graph_context is None:
            return
        best = self._require_best()
        incumbent_elite = self.pool.parents_by_fingerprint.get(self.pool.fingerprint(best).output_fingerprint)
        sources = [(best, incumbent_elite["profile"] if incumbent_elite is not None else self.profile)]
        sources.extend((elite["candidate"], elite["profile"]) for elite in self.pool.elites)
        for candidate, profile in sources:
            parent = _parent_from_candidate(candidate, operations=self.operations, graph_context=self.graph_context)
            if parent is None:
                continue
            effective = replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                                candidate_policy=IG_CANDIDATE_POLICY)
            self.solution_pool.add(PoolEntry(order=parent.order, score=tuple(candidate["score"]), candidate=candidate,
                                             batch_order=parent.batch_order, resource_overrides=parent.inherited, profile=effective))
        if not self.report["pool"]["initial_entries"]:
            self.report["pool"]["initial_entries"] = len(self.solution_pool.entries)

    def iterate_once(self) -> None:
        """One-shot driver; the shared stage uses the same iteration's resumable steps."""
        iteration = IGIteration(self)
        while iteration.step():
            pass

    def _reference_for_iteration(self) -> PoolEntry:
        reference = self.reference
        if reference is None:
            raise RuntimeError("Iterated greedy iteration started without a reference solution.")
        if self.non_improving >= self.limits.stagnation_iterations:
            self.non_improving = 0
            self._seed_solution_pool()
            restart = self.solution_pool.pick(self.pool_rnd, exclude_entry=reference)
            if restart is not None and restart.decision_key() != reference.decision_key():
                self._activate_entry(restart)
                if not restart.decoded_order:
                    decoded = self._decode_entry(restart.order)
                    if decoded is None:
                        self._activate_entry(reference)
                        return reference
                    restart = decoded
                    self.solution_pool.refresh(restart)
                self.report["pool"]["restarts"] += 1
                self.rotation.reset_sizes()
                self.idle_iterations = 0
                self.rejected_iterations = 0
                self.reference = reference = restart
        return reference

    def _accept_walk(self, entry: PoolEntry, reference: PoolEntry) -> None:
        report = self.report
        self.scale.observe(entry.score, reference.score)
        self.solution_pool.refresh(entry)
        if entry.score <= reference.score:
            accepted = True
        else:
            progress = (self.clock() - self.started) / max(self.deadline - self.started, 1e-9)
            temperature = self.cooling.temperature(self.scale.value, progress)
            accepted = sa_accept(entry.score, reference.score, temperature=temperature, u=self.rnd.random())
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
        if entry.features is None:
            rows = {int(row.op_id): row for row in entry.candidate["results"]}
            starts: Dict[int, float] = {}
            machines: Dict[int, str] = {}
            for op_id in self.parent.order:
                row = rows.get(op_id)
                if row is None:
                    continue
                if row.start_time is not None:
                    starts[op_id] = (row.start_time - self.start_dt).total_seconds() / 3600.0
                machines[op_id] = str(row.machine_id or "")
            entry.features = {"starts": starts, "machines": machines, "signals": self._signals(entry.candidate)}
        return entry.features

    def _signals(self, candidate: Dict[str, Any]) -> Dict[int, float]:
        """Tardiness in hours past the metric due deadline, plus a hair for critical-path operations."""
        signals: Dict[int, float] = {}
        rows = {int(row.op_id): row for row in candidate["results"]}
        for op_id in self.parent.order:
            metric = self.metrics.get(op_id, {})
            row = rows.get(op_id)
            tardy = 0.0
            if row is not None and "due_deadline_hours" in metric:
                finish = (row.end_time - self.start_dt).total_seconds() / 3600.0
                tardy = max(finish - float(metric["due_deadline_hours"]), 0.0)
            signals[op_id] = tardy + (1e-3 if metric.get("is_on_critical_path") else 0.0)
        return signals

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
        entry = PoolEntry(order=order, score=score, candidate=candidate, checkpoints=captured, decoded_order=True,
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
            if checkpoints is not None and resume is None and exc.field == "decode_checkpoint" and (
                    exc.details or {}).get("reason") == "decode_checkpoint_unsupported_calendar":
                self.report["checkpoint_capture_rejections"] += 1
                self.report["decodes"] -= 1  # Signature validation rejected capture before the first SGS pick.
                self.checkpoints.disable("decode_checkpoint_unsupported_calendar")
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
        self.improved_incumbent = self.incumbent.consider(candidate, profile=self.profile) or self.improved_incumbent

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
