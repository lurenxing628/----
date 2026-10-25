"""Iterated greedy over the decoded operation order of the incumbent graph candidate.

Each iteration destroys part of the reference order with one of three OR-Tools-style neighbourhoods
(time window, resource window, tardy/random; successful-generator continuation, adaptive size), parks the removed
operations at their latest feasible rank and re-inserts them one at a time at the best of a bounded
set of topologically valid ranks, judged by the formal SGS decode. Trial decodes resume from the
reference decode's checkpoints; the iteration's final order is decoded in full again and must
reproduce the resumed trial bit for bit (fail-loud otherwise). The walk accepts by simulated annealing
with exponential cooling and restarts from a small solution pool after stagnation. Every complete
decode is also an improve-only candidate for the incumbent. The stage retains its iteration and
decode caps while the common decode session owns admission, actual costs and shared request reuse.

The parent order is the parent's decoded start-time operation order with its explicit resource overrides
(``_parent_from_candidate``); re-decoding it under the IG context may reproduce the parent or drift, and that
drift is search freedom (2026-09-18: pick-sequence identities and pinned resources measured worse). Reference
captures are accounted as captures (reproduced or divergent), not as rejected or improving search decodes.
"""
from __future__ import annotations

import random
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple
from typing import OrderedDict as OrderedDictType

from core.algorithm_runtime.checkpoint_inputs import input_value
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpoint, decode_output_contents
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

from .context import reason_from_validation
from .decode_capture import capture_failure_reason, is_capture_failure
from .iterated_greedy_acceptance import (
    ExponentialCooling,
    PoolEntry,
    SolutionPool,
    TemperatureScale,
    profile_identity,
    sa_accept,
)
from .iterated_greedy_checkpoints import CheckpointStore
from .iterated_greedy_contract import (
    IG_PHASE,
    IteratedGreedyLimits,
    _BudgetExhausted,
    ig_decode_profile,
)
from .iterated_greedy_features import entry_features
from .iterated_greedy_incumbent import IGIncumbentTracker
from .iterated_greedy_incumbent import feasible_candidate as _feasible
from .iterated_greedy_moves import _Parent
from .iterated_greedy_neighborhoods import GeneratorRotation, build_generators
from .iterated_greedy_reference import adopt_incumbent, reference_for_iteration
from .iterated_greedy_start import start_reference
from .repair_decisions import RepairDecision
from .reporting import append_graph_attempt, record_rejected_attempt
from .v2_contract import is_graph_ready_v2_contract_error

# Pending output contents share one complete decode's row budget and a bounded LRU.
_PENDING_OUTPUT_CACHE_SIZE = 32
_STOP_BY_BUDGET = ("time_budget", "decode_budget", "decode_would_overrun", "estimated_decode_cost")
_FAILED = ((), False)
# Helpers reachable through this module for existing callers and tests.
__all__ = ["_IteratedGreedySearch", "_BudgetExhausted", "_Parent", "_publish"]


class _IteratedGreedySearch:
    def __init__(self, *, limits: IteratedGreedyLimits, parent: _Parent, profile: GraphReadyWeightProfile, pool: Any,
                 evaluate: Callable[..., Dict[str, Any]], metrics_by_op_id: Dict[int, Dict[str, Any]], start_dt: Any,
                 seed: int, deadline: float, clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                 improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool, report: Dict[str, Any],
                 decode_session: SharedDecodeSession, operations: List[Any],
                 graph_context: Dict[str, Any]) -> None:
        self.limits = limits
        self.parent = parent
        self.operations = operations
        self.graph_context = graph_context
        self.profile = ig_decode_profile(profile)
        self.pool = pool
        self.evaluate = evaluate
        self.decode_session = decode_session
        self.last_decode_skip: Optional[SharedSearchSkip] = None
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
        self.scored_decodes = 0
        # Annotate with typing.OrderedDict: subscripting collections.OrderedDict needs Python 3.9 (PEP 585).
        self.pending_outputs: OrderedDictType[Tuple[int, ...], Tuple[Any, Any, int]] = OrderedDict()
        self.pending_output_rows = 0
        self.decoded_entries: OrderedDictType[Tuple[int, ...], PoolEntry] = OrderedDict()
        self.decode_seconds_total = 0.0
        self.decode_count = 0
        self.incumbent = IGIncumbentTracker(pool=pool, report_state=report_state, report=report,
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
        self.incumbent.adopt_best(candidate)

    def _require_best(self) -> Dict[str, Any]:
        """The stage installs the incumbent before any pool seeding or decode."""
        best = self.best
        if best is None:
            raise RuntimeError("Iterated greedy has no incumbent candidate.")
        return best

    # ---- driver -------------------------------------------------------------------------------------------------------
    def _start_reference(self) -> None:
        """Choose an existing quality tier and formally check an optional constructive start."""
        start_reference(self)

    def adopt_incumbent(self, candidate: Dict[str, Any], profile: Optional[GraphReadyWeightProfile]) -> None:
        """Another stage improved the incumbent: base the walk on it, as OR-Tools LNS bases on the shared best."""
        adopt_incumbent(self, candidate, profile)

    def _set_parent(self, parent: _Parent, profile: GraphReadyWeightProfile, *, count_switch: bool = True) -> None:
        effective = ig_decode_profile(profile)
        before = (self.parent.batch_order, self.parent.inherited, profile_identity(self.profile))
        after = (parent.batch_order, parent.inherited, profile_identity(effective))
        self.parent, self.profile = parent, effective
        if before != after:
            self.scores.clear()
            self.pending_outputs.clear()
            self.pending_output_rows = 0
            self.decoded_entries.clear()
            if count_switch:
                self.report["context_switches"] += 1

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

    def _record_local_reuse(self, execution_kind: str, candidate: Optional[Dict[str, Any]] = None) -> None:
        """Describe local trial/reference reuse without inventing a decoder call or archive improvement."""
        receipt = (candidate or {}).get("decode_receipt") or {}
        self.decode_session.record_local_reuse(
            execution_kind=execution_kind, objective_name=self.report["objective_name"],
            request_id=receipt.get("request_id"), entry_id=(candidate or {}).get("_shared_entry_id"))

    def _features(self, entry: PoolEntry) -> Dict[str, Any]:
        return entry_features(self, entry)

    # ---- decoding and incumbent acceptance ----------------------------------------------------------------------------
    def _score_trial(self, order: Tuple[int, ...], reference: PoolEntry) -> Optional[Tuple[Tuple[float, ...], bool]]:
        self.last_decode_skip = None
        known = self.scores.get(order)
        if known is not None:
            self.report["duplicate_decision_pruned"] += 1
            self._record_local_reuse("local_trial_reused")
            return None if known is _FAILED else known
        resume = self.checkpoints.best_for(reference.checkpoints, base_order=reference.order, trial_order=order)
        if resume is not None:
            budget = self.decode_session.budget
            if (self.report["decodes"] + 1 >= self.limits.max_decodes
                    or (budget is not None
                        and not budget.can_afford_decode("sgs_resume", reserve_full=True)
                        and budget.can_afford_decode("sgs_full"))):
                resume = None
        try:
            candidate = self._decode(order, resume=resume)
        except SharedSearchSkip as exc:
            self.last_decode_skip = exc
            if exc.reason == "estimated_decode_cost":
                raise _BudgetExhausted(exc.reason) from exc
            return None
        if candidate is None:
            # A rejected decision is not retried; the rejection reason is already recorded.
            self.scores[order] = _FAILED
            return None
        score = tuple(candidate["score"])
        feasible = _feasible(candidate)
        scored = (score, feasible)
        receipt = candidate.get("decode_receipt") or {}
        self.scores[order] = scored
        self.scored_decodes += int(receipt.get("actual_decoder_calls", 1) > 0)
        verified = bool(receipt.get("verified", resume is None))
        if resume is not None and not verified:
            self._remember_output(order, candidate)
            if feasible and (self.best is None or score < tuple(self.best["score"])):
                self.report["validation_decodes"] += 1
                verified_entry = self._decode_entry(order)
                if verified_entry is None:
                    return None
                return verified_entry.score, True
        return scored

    def _decode_entry(self, order: Tuple[int, ...], *, redecode_reason: Optional[str] = None) -> Optional[PoolEntry]:
        """Full decode with checkpoints; must reproduce an earlier resumed decode of the same order."""
        self.last_decode_skip = None
        if self.scores.get(order) is _FAILED:
            self.report["duplicate_decision_pruned"] += 1
            self._record_local_reuse("local_trial_reused")
            return None
        known = self.decoded_entries.get(order)
        if known is not None:
            self.decoded_entries.move_to_end(order)
            self.report["duplicate_decision_pruned"] += 1
            self._record_local_reuse("reference_reused", known.candidate)
            return known
        recapture = order in self.scores and order not in self.pending_outputs
        request, captured = self.checkpoints.request_for(len(order))
        if redecode_reason is None:
            if order in self.pending_outputs:
                redecode_reason = "validate_trial"
            elif recapture:
                redecode_reason = "capture_checkpoints"
        try:
            candidate = self._decode(order, checkpoints=request, redecode_reason=redecode_reason)
        except SharedSearchSkip as exc:
            self.last_decode_skip = exc
            if exc.reason == "estimated_decode_cost":
                # This required full reconstruction cannot become affordable as run time decreases.
                raise _BudgetExhausted(exc.reason) from exc
            return None
        if candidate is None:
            if self._take_output(order) is not None:
                self._equivalence_violation()
            self.scores[order] = _FAILED
            return None
        # A full trial may need one new decode to capture a future reference's checkpoints.
        self.report["reference_capture_decodes"] += int(recapture)
        feasible = _feasible(candidate)
        score = tuple(candidate["score"])
        self.scores[order] = (score, feasible)
        self.scored_decodes += int((candidate.get("decode_receipt") or {}).get("actual_decoder_calls", 1) > 0)
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

    def _remember_output(self, order: Tuple[int, ...], candidate: Dict[str, Any]) -> None:
        previous = self.pending_outputs.pop(order, None)
        if previous is not None:
            self.pending_output_rows -= previous[2]
        row_count = len(candidate["results"])
        # Release old contents before freezing a new complete output.
        while len(self.pending_outputs) >= _PENDING_OUTPUT_CACHE_SIZE or self.pending_output_rows:
            self._take_output(next(iter(self.pending_outputs)))
        self.pending_outputs[order] = (
            decode_output_contents(candidate["results"], candidate["summary"]),
            input_value(tuple(candidate["score"]), field="decode_output.score"), row_count,
        )
        self.pending_output_rows += row_count

    def _take_output(self, order: Tuple[int, ...]) -> Optional[Tuple[Any, Any, int]]:
        expected = self.pending_outputs.pop(order, None)
        if expected is not None:
            self.pending_output_rows -= expected[2]
            self.scores.pop(order, None)
        return expected

    def _decode(self, order: Tuple[int, ...], *, resume: Optional[DecodeCheckpoint] = None,
                checkpoints: Optional[Any] = None, redecode_reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        decision = RepairDecision._unvalidated(self.parent.batch_order, tuple(order), self.parent.inherited)
        batch_order = list(decision.batch_order)
        decode_kwargs: Dict[str, Any] = {"decode_session": self.decode_session, "redecode_reason": redecode_reason}
        if resume is not None:
            decode_kwargs["decode_resume"] = resume
        if checkpoints is not None:
            decode_kwargs["decode_checkpoints"] = checkpoints
        decode_started = self.clock()
        try:
            candidate = self.evaluate(profile=self.profile, order=batch_order, repair_decision=decision,
                                      repair_parent=self.parent.prepared, before_decode=self._before_decode, **decode_kwargs)
        except ValidationError as exc:
            if checkpoints is not None and is_capture_failure(exc, resumed=resume is not None):
                # Capture refused or lost before the decode finished: degrade to plain full decodes, report why.
                self.report["checkpoint_capture_rejections"] += 1
                self.checkpoints.disable(capture_failure_reason(exc))
                return self._decode(order, redecode_reason=redecode_reason)
            if self.strict_mode or is_graph_ready_v2_contract_error(exc) or exc.field in (
                    "graph_ready_elite_repair", "graph_ready_iterated_greedy", "decode_checkpoint"):
                raise
            reason = reason_from_validation(exc)
            self.incumbent.reject(reason)
            best = self._require_best()
            record_rejected_attempt(attempts=self.attempts, strategy=best["strategy"], dispatch_rule=best["dispatch_rule"],
                                    reason=reason, message=str(exc), profile_slug=self.profile.slug)
            return None
        receipt = candidate.get("decode_receipt") or {}
        actual_calls = int(receipt.get("actual_decoder_calls", 1))
        if actual_calls:
            self.decode_seconds_total += max(self.clock() - decode_started, 0.0)
            self.decode_count += 1
            self.report["mean_decode_ms"] = self.decode_seconds_total * 1000.0 / self.decode_count
            self.checkpoints.note_decode(len(order), resumed_from=resume)
        verified = bool(receipt.get("verified", resume is None))
        if resume is not None and not verified:
            reference = self.incumbent.best
            self.incumbent.observe_trial(candidate)
            append_graph_attempt(attempts=self.attempts, candidate=candidate, profile=self.profile, reference=reference,
                                 accepted=False, search_report_state=self.incumbent.report_state,
                                 clock=self.clock, t_begin=self.t_begin, verified=False)
        else:
            expected = self._take_output(order)
            if expected is not None:
                self.checkpoints.equivalence_checks += 1
                actual = (decode_output_contents(candidate["results"], candidate["summary"]),
                          input_value(tuple(candidate["score"]), field="decode_output.score"))
                if actual != expected[:2]:
                    self._equivalence_violation()
            self._consider_for_incumbent(candidate)
        return candidate

    def _before_decode(self) -> None:
        self._require_budget()
        self.report["decodes"] += 1

    def _consider_for_incumbent(self, candidate: Dict[str, Any]) -> None:
        def record_decision(reference, accepted, comparison_kind):
            append_graph_attempt(attempts=self.attempts, candidate=candidate, profile=self.profile, reference=reference,
                                 accepted=accepted, search_report_state=self.incumbent.report_state,
                                 clock=self.clock, t_begin=self.t_begin, comparison_kind=comparison_kind)
        improved = self.incumbent.consider(candidate, profile=self.profile, capture_of=self.capturing,
                                          on_decision=record_decision)
        self.improved_incumbent = improved or self.improved_incumbent

    def _finish_report(self) -> None:
        report = self.report
        report["status"] = "strict_improvement" if report["accepted"] else "no_strict_improvement"
        if not report["decodes"] and report["stop_reason"] in _STOP_BY_BUDGET:
            report["status"] = "skipped_by_budget"
        report["generators"] = {generator.name: generator.summary() for generator in self.generators}
        report["checkpoints"] = self.checkpoints.summary()
        report["acceptance"]["temperature_scale"] = self.scale.value or None
        report["acceptance"]["secondary_temperature_scale"] = self.scale.secondary or None
        report["pool"]["entries"] = len(self.solution_pool.entries)


def _publish(report: Dict[str, Any], *, attempts: List[Dict[str, Any]]) -> None:
    attempts.append({"tag": IG_PHASE, "candidate_status": "phase_summary", "iterated_greedy": report})
