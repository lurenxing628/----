"""Account for IG trials separately from publishing a verified, strictly better incumbent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.candidate_fingerprint import score_strictly_better
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
)

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


def feasible_candidate(candidate: Dict[str, Any]) -> bool:
    return not candidate["summary"].failed_ops and bool(candidate["summary"].success)


class IGIncumbentTracker:
    def __init__(self, *, pool: Any, report_state: OptimizationSearchReportState, report: Dict[str, Any]) -> None:
        self.pool = pool
        self.report_state = report_state
        self.report = report
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

    def consider(self, candidate: Dict[str, Any], *, capture_of: Optional[Dict[str, Any]]) -> bool:
        """Publish a strictly better, unseen, feasible full decode.

        ``capture_of`` marks a reference capture: re-decoding a known solution under the IG context. A capture
        that reproduces its source is never a rejection; a divergent capture is a new solution and may still
        improve the incumbent, counted apart from destroy/repair improvements.
        """
        incumbent = self.best
        parent = self.best_identity
        fingerprint = self.pool.fingerprint(candidate, parent)
        self.pool.seen_outputs.add(fingerprint.output_key)
        self.report_state.mark_candidate_evaluated(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                                                   fingerprint=fingerprint)
        if capture_of is not None and self._capture_reproduced(fingerprint, capture_of):
            return False
        if not self._can_accept(candidate, incumbent=incumbent, fingerprint=fingerprint):
            return False
        self.report_state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                                                  fingerprint=fingerprint)
        self.report["accepted"] = True
        if capture_of is None:
            self.report["improvements"] += 1
        self.adopt_best(candidate, fingerprint=fingerprint)
        return True

    def _capture_reproduced(self, fingerprint: Any, capture_of: Dict[str, Any]) -> bool:
        """A reference capture that reproduces its source stops here; a divergent one goes on."""
        source = self.best_identity if capture_of is self.best else self.pool.fingerprint(capture_of)
        return bool(fingerprint.output_key == source.output_key)

    def _can_accept(self, candidate: Dict[str, Any], *, incumbent: Optional[Dict[str, Any]],
                    fingerprint: Any) -> bool:
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            return False
        if not feasible_candidate(candidate):
            return False
        if not score_strictly_better(candidate["score"], (incumbent or {}).get("score")):
            return False
        return candidate_is_preferred(
            candidate=candidate, incumbent=incumbent, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
            incumbent_origin=str((incumbent or {}).get("candidate_origin") or "baseline"),
            candidate_fingerprint=fingerprint,
            incumbent_fingerprint_changed=self.report_state.best_fingerprint_changed(),
        )


__all__ = ["IGIncumbentTracker", "feasible_candidate"]
