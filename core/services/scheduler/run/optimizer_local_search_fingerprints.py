from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Tuple

from .optimizer_candidate_fingerprint import CandidateFingerprint, build_candidate_fingerprint
from .optimizer_neighborhood_moves import NeighborhoodMove

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


class LocalSearchFingerprintTracker:
    def __init__(self, *, objective_name: str, initial_best: Dict[str, Any]) -> None:
        self.objective_name = str(objective_name)
        self.best_output_fingerprint: Optional[str] = None
        self.seen_output_fingerprints: Set[str] = set()
        initial = build_candidate_fingerprint(
            initial_best,
            objective_name=self.objective_name,
            parent_fingerprint=None,
            seen_output_fingerprints=set(),
        )
        self.best_output_fingerprint = initial.output_fingerprint
        self.seen_output_fingerprints.add(initial.output_fingerprint)

    def mark_evaluated(self, candidate: Dict[str, Any]) -> CandidateFingerprint:
        fingerprint = build_candidate_fingerprint(
            candidate,
            objective_name=self.objective_name,
            parent_fingerprint=self.best_output_fingerprint,
            seen_output_fingerprints=self.seen_output_fingerprints,
        )
        self.seen_output_fingerprints.add(fingerprint.output_fingerprint)
        return fingerprint

    def mark_best(self, fingerprint: CandidateFingerprint) -> None:
        self.best_output_fingerprint = fingerprint.output_fingerprint


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


def move_seen_key(move: NeighborhoodMove) -> Tuple[Any, ...]:
    if move.decision_key:
        return tuple(move.decision_key)
    return tuple(move.batch_order or ())


def should_skip_seen(move: NeighborhoodMove, seen_hashes: Optional[set]) -> bool:
    if seen_hashes is None:
        return False
    cand_hash = move_seen_key(move)
    if cand_hash in seen_hashes:
        return True
    seen_hashes.add(cand_hash)
    return False


__all__ = [
    "LocalSearchFingerprintTracker",
    "local_candidate_fingerprint",
    "move_seen_key",
    "should_skip_seen",
]
