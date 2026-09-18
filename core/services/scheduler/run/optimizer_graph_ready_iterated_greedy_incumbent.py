"""Account for IG trials separately from publishing a verified, strictly better incumbent."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .optimizer_candidate_comparison import candidate_is_preferred
from .optimizer_graph_ready_acceptance import build_graph_ready_improve_only_acceptance_event
from .optimizer_graph_ready_profiles import GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, GraphReadyWeightProfile
from .optimizer_graph_ready_reporting import append_graph_trace


def feasible_candidate(candidate: Dict[str, Any]) -> bool:
    return not candidate["summary"].failed_ops and bool(candidate["summary"].success)


class IGIncumbentTracker:
    def __init__(self, *, pool: Any, report_state: Any, report: Dict[str, Any], seed: int,
                 clock: Callable[[], float], t_begin: float, improvement_trace: List[Dict[str, Any]]) -> None:
        self.pool = pool
        self.report_state = report_state
        self.report = report
        self.seed = int(seed)
        self.clock = clock
        self.t_begin = t_begin
        self.improvement_trace = improvement_trace
        self.best: Optional[Dict[str, Any]] = None

    def observe_trial(self, candidate: Dict[str, Any]) -> None:
        """A resumed trial was evaluated, but cannot suppress or replace a subsequently verified solution."""
        if self.report_state is not None:
            self.report_state.mark_candidate_evaluated(
                candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, remember_fingerprint=False)
        self.report["unverified_trial_decodes"] += 1

    def consider(self, candidate: Dict[str, Any], *, profile: GraphReadyWeightProfile,
                 capture_of: Optional[Dict[str, Any]] = None) -> bool:
        """Publish a strictly better, unseen, feasible full decode.

        ``capture_of`` marks a reference capture: re-decoding a known solution under the IG context. A capture
        that reproduces its source is accounted as a capture, never as a rejection; a divergent capture is a new
        solution and may still improve the incumbent, counted apart from destroy/repair improvements.
        """
        incumbent = self.best
        fingerprint = self.pool.fingerprint(candidate, self.pool.fingerprint(incumbent).output_fingerprint)
        self.pool.seen_outputs.add(fingerprint.output_fingerprint)
        state_fingerprint = None
        if self.report_state is not None:
            state_fingerprint = self.report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN)
        if capture_of is not None and self._capture_reproduced(fingerprint, capture_of):
            return False
        event = self._acceptance_event(candidate, incumbent=incumbent, fingerprint=fingerprint,
                                       state_fingerprint=state_fingerprint)
        if event is None:
            return False
        if self.report_state is not None:
            self.report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, acceptance_event=event)
        append_graph_trace(improvement_trace=self.improvement_trace, candidate=candidate, profile=profile,
                           clock=self.clock, t_begin=self.t_begin)
        self.report["accepted"] = True
        self.report["reference_capture_improvements" if capture_of is not None else "improvements"] += 1
        self.best = candidate
        return True

    def _capture_reproduced(self, fingerprint: Any, capture_of: Dict[str, Any]) -> bool:
        """A reference capture that reproduces its source is accounted as a capture; a divergent one goes on."""
        if fingerprint.output_fingerprint == self.pool.fingerprint(capture_of).output_fingerprint:
            self.report["reference_captures"] += 1
            return True
        self.report["reference_capture_divergences"] += 1
        return False

    def _acceptance_event(self, candidate: Dict[str, Any], *, incumbent: Optional[Dict[str, Any]], fingerprint: Any,
                          state_fingerprint: Any) -> Optional[Dict[str, Any]]:
        """Return the improve-only acceptance event, or None after recording why the candidate is rejected."""
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            already = state_fingerprint is not None and (state_fingerprint.same_as_parent or state_fingerprint.same_as_seen)
            self.reject("same_fingerprint", record=not already)
            return None
        if not feasible_candidate(candidate):
            self.reject("ig_infeasible")
            return None
        event = build_graph_ready_improve_only_acceptance_event(
            candidate_score=candidate["score"], incumbent_score=(incumbent or {}).get("score"), seed=self.seed)
        if event is None:
            self.reject("no_strict_improvement")
            return None
        if not candidate_is_preferred(
                candidate=candidate, incumbent=incumbent, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                incumbent_origin=str((incumbent or {}).get("candidate_origin") or "baseline"),
                candidate_fingerprint=fingerprint,
                incumbent_fingerprint_changed=bool(self.report_state and self.report_state.best_fingerprint_changed())):
            self.reject("acceptance_rejected")
            return None
        return event

    def reject(self, reason: str, *, record: bool = True) -> None:
        reasons = self.report["rejected_by_reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
        if record and self.report_state is not None:
            self.report_state.mark_candidate_rejected(reason=reason)


def incumbent_events(report: Dict[str, Any]) -> int:
    """Strict incumbent improvements published by the stage, whatever produced them."""
    return int(report["improvements"]) + int(report["reference_capture_improvements"])


__all__ = ["IGIncumbentTracker", "feasible_candidate", "incumbent_events"]
