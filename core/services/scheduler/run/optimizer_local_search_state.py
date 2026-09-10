from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .optimizer_candidate_comparison import candidate_is_preferred
from .optimizer_candidate_fingerprint import CandidateFingerprint


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

    def reset_current_to_best(self) -> None:
        """把 current 完全对齐回 best：order/score/results 三者必须同源。

        restart 的扰动顺序不允许从这里塞入——未评估的顺序配上 best 的 score/results
        会让接受准则参照错误基准分数、邻域用陈旧 results 选靶（A01）。扰动顺序必须
        先经 schedule_fn 真实评估成候选，再走 accept_current 对齐三元组。
        """
        self.current = self.best
        self.current_order = list(self.best.get("order") or [])
        best_resource_pool = self.best.get("resource_pool")
        self.current_resource_pool = dict(best_resource_pool) if isinstance(best_resource_pool, dict) else {}


def candidate_can_update_best(
    *,
    candidate: Dict[str, Any],
    best: Dict[str, Any],
    fingerprint: Optional[CandidateFingerprint],
    candidate_origin: str = "local_search",
    incumbent_origin: str = "baseline",
    incumbent_fingerprint_changed: bool = False,
) -> bool:
    if fingerprint is None:
        return False
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
        dict(source["params"] or {}),
        str(source.get("dispatch_mode") or dispatch_mode_cfg),
        str(source.get("dispatch_rule") or dispatch_rule_cfg),
    )


__all__ = ["LocalSearchState", "candidate_can_update_best", "resolve_current_strategy_state"]
