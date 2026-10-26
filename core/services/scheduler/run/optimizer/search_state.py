from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


def score_tuple(score: Optional[Sequence[float]]) -> Tuple[float, ...]:
    # 跳过、阶段汇总这类尝试不带分数，排在所有已评分尝试之后；已评分尝试的分数
    # 是解码算出的非空数字列表。
    if score is None:
        return (float("inf"),)
    return tuple(score)


def _attempt_dispatch_mode(item: Dict[str, Any]) -> str:
    return str(item.get("dispatch_mode") or "")


def _attempt_tag(item: Dict[str, Any]) -> str:
    # Every attempts.append construction point writes a non-empty tag.
    return item["tag"]


def is_candidate_rejected_attempt(item: Dict[str, Any]) -> bool:
    return item.get("source") == "candidate_rejected"


def attempt_identity(item: Dict[str, Any]) -> Tuple[str, ...]:
    if is_candidate_rejected_attempt(item):
        # Rejected attempts come only from attempt_records/grasp_ig_candidates with these fields filled;
        # origin.field mirrors ValidationError.field, which may be None.
        origin = item["origin"]
        return (
            "candidate_rejected",
            item["tag"],
            item["strategy"],
            item["dispatch_mode"],
            item["dispatch_rule"],
            origin["type"],
            str(origin.get("field") or ""),
            origin["message"],
        )
    return ("scored", _attempt_tag(item))


def append_unique_rejected_attempt(attempts: List[Dict[str, Any]], attempt: Dict[str, Any]) -> None:
    identity = attempt_identity(attempt)
    if any(attempt_identity(item) == identity for item in attempts):
        return
    attempts.append(attempt)


def _unique_rejected_attempts(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for item in attempts:
        if is_candidate_rejected_attempt(item):
            append_unique_rejected_attempt(selected, item)
    return selected


def _compact_scored_attempts(attempts: List[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    scored = [(score_tuple(item.get("score")), index, item) for index, item in enumerate(attempts)]
    best_by_mode: Dict[str, Tuple[Tuple[float, ...], Dict[str, Any]]] = {}
    for sc, _idx, item in scored:
        mode = _attempt_dispatch_mode(item)
        if mode not in best_by_mode or sc < best_by_mode[mode][0]:
            best_by_mode[mode] = (sc, item)
    selected = list(best_by_mode.values())
    selected_tags = {_attempt_tag(item) for _sc, item in selected}
    for sc, _idx, item in sorted(scored, key=lambda row: (row[0], row[1])):
        if len(selected) >= limit:
            break
        tag = _attempt_tag(item)
        if tag in selected_tags:
            continue
        selected.append((sc, item))
        selected_tags.add(tag)
    selected.sort(key=lambda pair: pair[0])
    return [item for _sc, item in selected[:limit]]


def _rejected_attempt_limit(*, scored_count: int, rejected_count: int, limit: int) -> int:
    scored_floor = min(int(scored_count), max(int(limit) - 1, 0))
    return min(int(rejected_count), max(int(limit) - scored_floor, 0))


def compact_attempts(attempts: List[Dict[str, Any]], *, limit: int = 12) -> List[Dict[str, Any]]:
    raw_attempts = list(attempts)
    if len(raw_attempts) <= limit:
        return raw_attempts
    scored_attempts = [item for item in raw_attempts if not is_candidate_rejected_attempt(item)]
    selected_scored = _compact_scored_attempts(scored_attempts, limit=limit)
    rejected_attempts = _unique_rejected_attempts(raw_attempts)
    rejected_limit = _rejected_attempt_limit(scored_count=len(selected_scored), rejected_count=len(rejected_attempts), limit=limit)
    selected_rejected = rejected_attempts[:rejected_limit]
    return selected_scored[: limit - len(selected_rejected)] + selected_rejected


@dataclass
class OptimizerSearchState:
    best: Optional[Dict[str, Any]] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    improvement_trace: List[Dict[str, Any]] = field(default_factory=list)

    def compact_attempts(self, *, limit: int = 12) -> List[Dict[str, Any]]:
        return compact_attempts(self.attempts, limit=limit)
