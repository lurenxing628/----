from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .candidate_comparison import candidate_is_preferred
from .candidate_fingerprint import CandidateFingerprint


@dataclass
class LocalSearchState:
    current: Dict[str, Any]
    best: Dict[str, Any]
    current_order: List[str]
    current_resource_pool: Optional[Dict[str, Any]]
    current_resource_pair_rank: Dict[Tuple[str, str], int]

    @classmethod
    def from_best(cls, best: Dict[str, Any], *, resource_pool: Optional[Dict[str, Any]]) -> LocalSearchState:
        return cls(
            current=best,
            best=best,
            current_order=list(best["order"]),
            # Every candidate carries the run's own pool normalized as ``resource_pool or {}``.
            current_resource_pool=resource_pool or {},
            current_resource_pair_rank=best.get("resource_pair_rank") or {},
        )

    def accept_current(self, candidate: Dict[str, Any]) -> None:
        self.current = candidate
        self.current_resource_pair_rank = candidate["resource_pair_rank"]
        self.current_order = list(candidate.get("order") or self.current_order)
        candidate_resource_pool = candidate.get("resource_pool")
        if isinstance(candidate_resource_pool, dict):
            self.current_resource_pool = candidate_resource_pool

    def improve_best(self, candidate: Dict[str, Any]) -> None:
        self.best = candidate
        self.accept_current(candidate)


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
    *,
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
) -> Tuple[Any, Dict[str, Any], str, str]:
    return (
        source["strategy"],
        dict(source["params"]),
        str(source.get("dispatch_mode") or dispatch_mode_cfg),
        str(source.get("dispatch_rule") or dispatch_rule_cfg),
    )


__all__ = ["LocalSearchState", "candidate_can_update_best", "resolve_current_strategy_state"]
