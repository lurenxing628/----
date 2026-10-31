from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .candidate_comparison import candidate_is_preferred
from .candidate_fingerprint import CandidateFingerprint
from .neighborhood_move_support import LocalSearchResultFacts, prepare_batch_due_dates


@dataclass
class LocalSearchState:
    current: Dict[str, Any]
    best: Dict[str, Any]
    current_order: List[str]
    current_resource_pool: Dict[str, Any]
    current_resource_pair_rank: Dict[Tuple[str, str], int]
    due_by_batch: Optional[Dict[str, Optional[date]]] = None
    current_facts: Optional[LocalSearchResultFacts] = None
    best_facts: Optional[LocalSearchResultFacts] = None

    @classmethod
    def from_best(
        cls,
        best: Dict[str, Any],
        *,
        batches: Optional[Dict[str, Any]] = None,
        due_by_batch: Optional[Dict[str, Optional[date]]] = None,
    ) -> LocalSearchState:
        resolved_due_by_batch = (
            due_by_batch
            if due_by_batch is not None
            else (prepare_batch_due_dates(batches) if batches is not None else None)
        )
        facts = LocalSearchResultFacts(best["results"], batches=batches, due_by_batch=resolved_due_by_batch)
        return cls(
            current=best,
            best=best,
            current_order=list(best["order"]),
            # Every candidate carries the run's own pool normalized as ``resource_pool or {}``.
            current_resource_pool=best["resource_pool"],
            current_resource_pair_rank=best.get("resource_pair_rank") or {},
            due_by_batch=resolved_due_by_batch,
            current_facts=facts,
            best_facts=facts,
        )

    def facts_for(
        self,
        results: List[Any],
        *,
        batches: Optional[Dict[str, Any]] = None,
    ) -> LocalSearchResultFacts:
        if batches is not None and self.due_by_batch is None:
            self.due_by_batch = prepare_batch_due_dates(batches)
        if self.current_facts is not None and self.current_facts.results is results:
            if batches is not None and self.current_facts._due_by_batch is None:
                self.current_facts._batches = batches
                self.current_facts._due_by_batch = self.due_by_batch
            return self.current_facts
        if self.best_facts is not None and self.best_facts.results is results:
            if batches is not None and self.best_facts._due_by_batch is None:
                self.best_facts._batches = batches
                self.best_facts._due_by_batch = self.due_by_batch
            return self.best_facts
        facts = LocalSearchResultFacts(results, batches=batches, due_by_batch=self.due_by_batch)
        if results is self.current["results"]:
            self.current_facts = facts
        if results is self.best["results"]:
            self.best_facts = facts
        return facts

    def accept_current(self, candidate: Dict[str, Any]) -> None:
        self.current = candidate
        self.current_resource_pair_rank = candidate["resource_pair_rank"]
        self.current_order = list(candidate["order"])
        self.current_resource_pool = candidate["resource_pool"]
        results = candidate["results"]
        if self.best_facts is not None and self.best_facts.results is results:
            self.current_facts = self.best_facts
        elif self.current_facts is None or self.current_facts.results is not results:
            self.current_facts = LocalSearchResultFacts(results, due_by_batch=self.due_by_batch)

    def set_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        results = candidate["results"]
        if self.current_facts is not None and self.current_facts.results is results:
            self.best_facts = self.current_facts
        elif self.best_facts is None or self.best_facts.results is not results:
            self.best_facts = LocalSearchResultFacts(results, due_by_batch=self.due_by_batch)

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
