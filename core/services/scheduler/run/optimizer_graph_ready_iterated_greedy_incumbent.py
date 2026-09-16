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

    def consider(self, candidate: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> bool:
        incumbent = self.best
        fingerprint = self.pool.fingerprint(candidate, self.pool.fingerprint(incumbent).output_fingerprint)
        self.pool.seen_outputs.add(fingerprint.output_fingerprint)
        state_fingerprint = None
        if self.report_state is not None:
            state_fingerprint = self.report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN)
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            already = state_fingerprint is not None and (state_fingerprint.same_as_parent or state_fingerprint.same_as_seen)
            self.reject("same_fingerprint", record=not already)
            return False
        if not feasible_candidate(candidate):
            self.reject("ig_infeasible")
            return False
        event = build_graph_ready_improve_only_acceptance_event(
            candidate_score=candidate["score"], incumbent_score=(incumbent or {}).get("score"), seed=self.seed)
        if event is None:
            self.reject("no_strict_improvement")
            return False
        if not candidate_is_preferred(
                candidate=candidate, incumbent=incumbent, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                incumbent_origin=str((incumbent or {}).get("candidate_origin") or "baseline"),
                candidate_fingerprint=fingerprint,
                incumbent_fingerprint_changed=bool(self.report_state and self.report_state.best_fingerprint_changed())):
            self.reject("acceptance_rejected")
            return False
        if self.report_state is not None:
            self.report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, acceptance_event=event)
        append_graph_trace(improvement_trace=self.improvement_trace, candidate=candidate, profile=profile,
                           clock=self.clock, t_begin=self.t_begin)
        self.report["accepted"] = True
        self.report["improvements"] += 1
        self.best = candidate
        return True

    def reject(self, reason: str, *, record: bool = True) -> None:
        reasons = self.report["rejected_by_reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
        if record and self.report_state is not None:
            self.report_state.mark_candidate_rejected(reason=reason)


__all__ = ["IGIncumbentTracker", "feasible_candidate"]
