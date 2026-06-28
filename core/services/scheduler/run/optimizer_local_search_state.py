from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .optimizer_candidate_fingerprint import CandidateFingerprint, score_strictly_better


@dataclass
class LocalSearchState:
    current: Dict[str, Any]
    best: Dict[str, Any]
    current_order: List[str]
    current_resource_pool: Optional[Dict[str, Any]]

    @classmethod
    def from_best(cls, best: Dict[str, Any], *, resource_pool: Optional[Dict[str, Any]]) -> LocalSearchState:
        return cls(
            current=best,
            best=best,
            current_order=list(best.get("order") or []),
            current_resource_pool=dict(resource_pool or best.get("resource_pool") or {}),
        )

    def accept_current(self, candidate: Dict[str, Any]) -> None:
        self.current = candidate
        self.current_order = list(candidate.get("order") or self.current_order)
        candidate_resource_pool = candidate.get("resource_pool")
        if isinstance(candidate_resource_pool, dict):
            self.current_resource_pool = dict(candidate_resource_pool)

    def improve_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        self.accept_current(candidate)

    def reset_current_to_best(self, *, order: List[str]) -> None:
        self.current = self.best
        self.current_order = list(order or self.best.get("order") or [])
        best_resource_pool = self.best.get("resource_pool")
        self.current_resource_pool = dict(best_resource_pool) if isinstance(best_resource_pool, dict) else {}


def candidate_can_update_best(
    *,
    candidate: Dict[str, Any],
    best: Dict[str, Any],
    fingerprint: Optional[CandidateFingerprint],
) -> bool:
    if not score_strictly_better(candidate.get("score"), best.get("score")):
        return False
    if fingerprint is None:
        return False
    if fingerprint.same_as_parent or fingerprint.same_as_seen:
        return False
    return True


__all__ = ["LocalSearchState", "candidate_can_update_best"]
