from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.algorithms.evaluation_completion import PreparedBatchDue

from .candidate_comparison import candidate_is_preferred
from .candidate_fingerprint import CandidateFingerprint
from .neighborhood_move_support import LocalSearchResultFacts


@dataclass
class LocalSearchState:
    current: Dict[str, Any]
    best: Dict[str, Any]
    current_order: List[str]
    current_resource_pool: Dict[str, Any]
    current_resource_pair_rank: Dict[Tuple[str, str], int]
    due_batches: Tuple[PreparedBatchDue, ...]
    current_facts: LocalSearchResultFacts
    best_facts: LocalSearchResultFacts

    @classmethod
    def from_best(cls, best: Dict[str, Any], *, due_batches: Tuple[PreparedBatchDue, ...]) -> LocalSearchState:
        facts = LocalSearchResultFacts(best["results"], due_batches=due_batches)
        return cls(
            current=best,
            best=best,
            current_order=list(best["order"]),
            # Every candidate carries the run's own pool normalized as ``resource_pool or {}``.
            current_resource_pool=best["resource_pool"],
            current_resource_pair_rank=best.get("resource_pair_rank") or {},
            due_batches=due_batches,
            current_facts=facts,
            best_facts=facts,
        )

    def accept_current(self, candidate: Dict[str, Any]) -> None:
        self.current = candidate
        self.current_resource_pair_rank = candidate["resource_pair_rank"]
        self.current_order = list(candidate["order"])
        self.current_resource_pool = candidate["resource_pool"]
        results = candidate["results"]
        if self.best_facts.results is results:
            self.current_facts = self.best_facts
        elif self.current_facts.results is not results:
            self.current_facts = LocalSearchResultFacts(results, due_batches=self.due_batches)

    def set_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        results = candidate["results"]
        if self.current_facts.results is results:
            self.best_facts = self.current_facts
        elif self.best_facts.results is not results:
            self.best_facts = LocalSearchResultFacts(results, due_batches=self.due_batches)

    def improve_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        self.accept_current(candidate)
        self.best_facts = self.current_facts


def candidate_can_update_best(
    *,
    candidate: Dict[str, Any],
    best: Dict[str, Any],
    fingerprint: CandidateFingerprint,
    candidate_origin: str,
    incumbent_origin: str,
    incumbent_fingerprint_changed: bool,
) -> bool:
    if fingerprint.same_as_parent or fingerprint.same_as_seen:
        return False
    return candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=candidate_origin,
        incumbent_origin=incumbent_origin,
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=bool(incumbent_fingerprint_changed),
    )


def resolve_current_strategy_state(
    source: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any], str, str]:
    return (
        source["strategy"],
        dict(source["params"]),
        str(source["dispatch_mode"]),
        str(source["dispatch_rule"]),
    )


__all__ = ["LocalSearchState", "candidate_can_update_best", "resolve_current_strategy_state"]
