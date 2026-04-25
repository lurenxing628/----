from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return (float("inf"),)
    out: List[float] = []
    for item in score:
        try:
            out.append(float(item))
        except Exception:
            out.append(float("inf"))
    return tuple(out)


def _attempt_dispatch_mode(item: Dict[str, Any]) -> str:
    return str(item.get("dispatch_mode") or "")


def _attempt_tag(item: Dict[str, Any]) -> str:
    return str(item.get("tag") or "")


def _sorted_attempts_by_score(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(list(attempts or []), key=lambda item: score_tuple(item.get("score")))


def _best_attempts_by_dispatch_mode(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_mode: Dict[str, Dict[str, Any]] = {}
    for item in attempts or []:
        mode = _attempt_dispatch_mode(item)
        current = best_by_mode.get(mode)
        if current is None or score_tuple(item.get("score")) < score_tuple(current.get("score")):
            best_by_mode[mode] = item
    return list(best_by_mode.values())


def _append_unique_best_attempts(
    selected: List[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    selected_tags = {_attempt_tag(item) for item in selected}
    for item in _sorted_attempts_by_score(attempts):
        tag = _attempt_tag(item)
        if tag in selected_tags:
            continue
        selected.append(item)
        selected_tags.add(tag)
        if len(selected) >= limit:
            break
    return selected


def compact_attempts(attempts: List[Dict[str, Any]], *, limit: int = 12) -> List[Dict[str, Any]]:
    if len(attempts or []) <= limit:
        return list(attempts or [])
    selected = _best_attempts_by_dispatch_mode(attempts)
    selected = _append_unique_best_attempts(selected, attempts, limit=limit)
    selected.sort(key=lambda item: score_tuple(item.get("score")))
    return selected[:limit]


def init_seen_hashes(cur_order: List[str], best: Optional[Dict[str, Any]]) -> Optional[set]:
    if len(cur_order) < 10:
        return None
    seen_hashes = {tuple(cur_order)}
    if isinstance(best, dict):
        best_order = tuple(best.get("order") or [])
        if best_order:
            seen_hashes.add(best_order)
    return seen_hashes


@dataclass
class OptimizerSearchState:
    best: Optional[Dict[str, Any]] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    improvement_trace: List[Dict[str, Any]] = field(default_factory=list)

    def compact_attempts(self, *, limit: int = 12) -> List[Dict[str, Any]]:
        return compact_attempts(self.attempts, limit=limit)

    def compact_trace(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        return list(self.improvement_trace or [])[:limit]
