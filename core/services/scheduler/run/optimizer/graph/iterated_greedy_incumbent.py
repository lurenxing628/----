"""Account for IG trials separately from publishing a verified, strictly better incumbent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.candidate_fingerprint import score_strictly_better
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
    GraphReadyWeightProfile,
)

from .reporting import append_graph_trace

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


def feasible_candidate(candidate: Dict[str, Any]) -> bool:
    return not candidate["summary"].failed_ops and bool(candidate["summary"].success)


class IGIncumbentTracker:
    def __init__(self, *, pool: Any, report_state: OptimizationSearchReportState, report: Dict[str, Any],
                 clock: Callable[[], float], t_begin: float, improvement_trace: List[Dict[str, Any]]) -> None:
        self.pool = pool
        self.report_state = report_state
        self.report = report
        self.clock = clock
        self.t_begin = t_begin
        self.improvement_trace = improvement_trace
        self.best: Optional[Dict[str, Any]] = None
        self.best_identity: Any = None

    def adopt_best(self, candidate: Optional[Dict[str, Any]], *, fingerprint: Any = None) -> None:
        if candidate is self.best and self.best_identity is not None and fingerprint is None:
            return
        self.best = candidate
        self.best_identity = None if candidate is None else fingerprint or self.pool.fingerprint(candidate)

    def observe_trial(self, candidate: Dict[str, Any]) -> None:
        """A resumed trial was evaluated, but cannot suppress or replace a subsequently verified solution."""
        self.report_state.mark_candidate_evaluated(
            candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, remember_fingerprint=False)
        self.report["unverified_trial_decodes"] += 1

    def consider(self, candidate: Dict[str, Any], *, profile: GraphReadyWeightProfile,
                 capture_of: Optional[Dict[str, Any]],
                 on_decision: Callable[[Optional[Dict[str, Any]], bool, str], None]) -> bool:
        """Publish a strictly better, unseen, feasible full decode.

        ``capture_of`` marks a reference capture: re-decoding a known solution under the IG context. A capture
        that reproduces its source is accounted as a capture, never as a rejection; a divergent capture is a new
        solution and may still improve the incumbent, counted apart from destroy/repair improvements.
        """
        incumbent = self.best
        parent = self.best_identity
        fingerprint = self.pool.fingerprint(candidate, parent)
        self.pool.seen_outputs.add(fingerprint.output_key)
        self.report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                                                   fingerprint=fingerprint)
        if capture_of is not None and self._capture_reproduced(fingerprint, capture_of):
            on_decision(capture_of, False, "reference_capture")
            return False
        if not self._can_accept(candidate, incumbent=incumbent, fingerprint=fingerprint):
            on_decision(incumbent, False, "incumbent")
            return False
        self.report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                                                  fingerprint=fingerprint)
        on_decision(incumbent, True, "incumbent")
        append_graph_trace(improvement_trace=self.improvement_trace, candidate=candidate, profile=profile,
                           clock=self.clock, t_begin=self.t_begin)
        self.report["accepted"] = True
        self.report["reference_capture_improvements" if capture_of is not None else "improvements"] += 1
        self.adopt_best(candidate, fingerprint=fingerprint)
        return True

    def _capture_reproduced(self, fingerprint: Any, capture_of: Dict[str, Any]) -> bool:
        """A reference capture that reproduces its source is accounted as a capture; a divergent one goes on."""
        source = self.best_identity if capture_of is self.best else self.pool.fingerprint(capture_of)
        if fingerprint.output_key == source.output_key:
            self.report["reference_captures"] += 1
            return True
        self.report["reference_capture_divergences"] += 1
        return False

    def _can_accept(self, candidate: Dict[str, Any], *, incumbent: Optional[Dict[str, Any]],
                    fingerprint: Any) -> bool:
        """Return True when the candidate can replace the incumbent, else record why it is rejected."""
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            self.reject("same_fingerprint")
            return False
        if not feasible_candidate(candidate):
            self.reject("ig_infeasible")
            return False
        if not score_strictly_better(candidate["score"], (incumbent or {}).get("score")):
            self.reject("no_strict_improvement")
            return False
        if not candidate_is_preferred(
                candidate=candidate, incumbent=incumbent, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                incumbent_origin=str((incumbent or {}).get("candidate_origin") or "baseline"),
                candidate_fingerprint=fingerprint,
                incumbent_fingerprint_changed=self.report_state.best_fingerprint_changed()):
            self.reject("acceptance_rejected")
            return False
        return True

    def reject(self, reason: str) -> None:
        reasons = self.report["rejected_by_reason"]
        reasons[reason] = reasons.get(reason, 0) + 1


__all__ = ["IGIncumbentTracker", "feasible_candidate"]
