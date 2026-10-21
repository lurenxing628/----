from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Tuple

from .candidate_fingerprint import CandidateFingerprint, build_candidate_fingerprint

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState


class LocalSearchFingerprintTracker:
    def __init__(self, *, objective_name: str, initial_best: Dict[str, Any],
                 initial_fingerprint: Optional[CandidateFingerprint] = None) -> None:
        self.objective_name = str(objective_name)
        self.best_identity: Optional[CandidateFingerprint] = None
        self._candidate_sequence = 1
        self.seen_output_fingerprints: Set[Tuple[Any, ...]] = set()
        if initial_fingerprint is not None:
            initial = initial_fingerprint.with_context(parent_fingerprint=None, seen_output_fingerprints=())
        else:
            initial = build_candidate_fingerprint(
                initial_best,
                objective_name=self.objective_name,
                parent_fingerprint=None,
                seen_output_fingerprints=set(),
                candidate_id=self._candidate_sequence,
            )
        self.best_identity = initial
        self.seen_output_fingerprints.add(initial.output_key)

    def mark_evaluated(self, candidate: Dict[str, Any]) -> CandidateFingerprint:
        self._candidate_sequence += 1
        fingerprint = build_candidate_fingerprint(
            candidate,
            objective_name=self.objective_name,
            parent_fingerprint=self.best_identity,
            seen_output_fingerprints=self.seen_output_fingerprints,
            candidate_id=self._candidate_sequence,
        )
        self.seen_output_fingerprints.add(fingerprint.output_key)
        return fingerprint

    def mark_best(self, fingerprint: CandidateFingerprint) -> None:
        self.best_identity = fingerprint


def local_candidate_fingerprint(
    *,
    search_report_state: Optional[OptimizationSearchReportState],
    fingerprint_tracker: LocalSearchFingerprintTracker,
    candidate: Optional[Dict[str, Any]],
):
    if candidate is None:
        return None
    if search_report_state is not None:
        return search_report_state.mark_candidate_evaluated(candidate, origin="local_search")
    return fingerprint_tracker.mark_evaluated(candidate)


__all__ = [
    "LocalSearchFingerprintTracker",
    "local_candidate_fingerprint",
]
