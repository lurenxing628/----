from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.algorithm_contracts.sort_strategies import WeightedParams
from core.algorithms.evaluation_completion import PreparedBatchDue
from core.models.enums import SortStrategy

from .candidate_comparison import candidate_is_preferred
from .candidate_fingerprint import CandidateFingerprint
from .neighborhood_move_support import LocalSearchResultFacts


@dataclass
class LocalSearchState:
    current: Dict[str, Any]
    best: Dict[str, Any]
    current_order: List[str]
    # Current's pair-rank overrides of the run's pool; a neighborhood move adds to them.
    current_resource_pair_rank: Mapping[Tuple[str, str], int]
    due_batches: Tuple[PreparedBatchDue, ...]
    current_facts: LocalSearchResultFacts
    best_facts: LocalSearchResultFacts

    @classmethod
    def from_best(cls, best: Dict[str, Any], *, due_batches: Tuple[PreparedBatchDue, ...]) -> LocalSearchState:
        facts = LocalSearchResultFacts(
            best["results"],
            due_batches=due_batches,
            finish_by_batch=best["metrics"]._finish_by_batch,
        )
        return cls(
            current=best,
            best=best,
            current_order=list(best["order"]),
            current_resource_pair_rank=best["resource_pair_rank"],
            due_batches=due_batches,
            current_facts=facts,
            best_facts=facts,
        )

    def accept_current(self, candidate: Dict[str, Any]) -> None:
        self.current = candidate
        self.current_resource_pair_rank = candidate["resource_pair_rank"]
        self.current_order = list(candidate["order"])
        # Facts derive from the results alone (finish_by_batch included), so a restart that reuses
        # archived results with freshly computed metrics keeps the facts already built for them.
        results = candidate["results"]
        if self.best_facts.results is results:
            self.current_facts = self.best_facts
        elif self.current_facts.results is not results:
            self.current_facts = LocalSearchResultFacts(
                results,
                due_batches=self.due_batches,
                finish_by_batch=candidate["metrics"]._finish_by_batch,
            )

    def set_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        results = candidate["results"]
        if self.current_facts.results is results:
            self.best_facts = self.current_facts
        elif self.best_facts.results is not results:
            self.best_facts = LocalSearchResultFacts(
                results,
                due_batches=self.due_batches,
                finish_by_batch=candidate["metrics"]._finish_by_batch,
            )

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


@dataclass(frozen=True)
class StrategyState:
    """The decode choices a local-search candidate takes over from the candidate it starts from.

    A graph-ready profile is not one of them: local search decodes with graph scoring off, so a move
    started from a graph-stage candidate records no profile.
    """

    strategy: SortStrategy
    params: Optional[WeightedParams]
    dispatch_mode: str
    dispatch_rule: str


def resolve_current_strategy_state(source: Dict[str, Any]) -> StrategyState:
    return StrategyState(source["strategy"], source["params"], source["dispatch_mode"], source["dispatch_rule"])


__all__ = ["LocalSearchState", "StrategyState", "candidate_can_update_best", "resolve_current_strategy_state"]
