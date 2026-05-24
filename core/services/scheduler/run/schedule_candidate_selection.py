from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError

from .schedule_candidate_health import HEALTH_BETTER
from .schedule_candidate_specs import CANDIDATE_KIND_BASELINE, CANDIDATE_KIND_CRITICAL_CHAIN

SELECTION_POLICY_SCORE_ONLY = "score_only"
SELECTION_POLICY_BALANCED = "balanced"

_SUPPORTED_POLICIES = (SELECTION_POLICY_SCORE_ONLY, SELECTION_POLICY_BALANCED)


@dataclass(frozen=True)
class CandidateSelectionResult:
    selected_candidate_key: str
    selected_kind: str
    selection_policy: str
    reason_code: str
    raw_score_best_key: str
    baseline_best_key: Optional[str]
    critical_best_key: Optional[str]
    critical_health_best_key: Optional[str]
    selected_score: Tuple[float, ...]
    selected_plan: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_candidate_key": self.selected_candidate_key,
            "selected_kind": self.selected_kind,
            "selection_policy": self.selection_policy,
            "reason_code": self.reason_code,
            "raw_score_best_key": self.raw_score_best_key,
            "baseline_best_key": self.baseline_best_key,
            "critical_best_key": self.critical_best_key,
            "critical_health_best_key": self.critical_health_best_key,
            "selected_score": list(self.selected_score),
        }


def select_candidate_plan(
    candidates: Sequence[Any],
    *,
    policy: str = SELECTION_POLICY_BALANCED,
    graph_overdue_tolerance_count: int = 1,
    graph_tardiness_tolerance_ratio: float = 0.10,
) -> CandidateSelectionResult:
    selection_policy = _normalize_policy(policy)
    completed = _completed_candidates(candidates)
    if not completed:
        raise ValidationError("试算方案都没算成功，无法自动选择采用结果。", field="candidate_selection")

    raw_score_best = min(completed, key=_candidate_sort_key)
    baseline_best = _best_of_kind(completed, CANDIDATE_KIND_BASELINE)
    critical_best = _best_of_kind(completed, CANDIDATE_KIND_CRITICAL_CHAIN)
    critical_health_best = _health_eligible_critical_best(critical_best)

    if selection_policy == SELECTION_POLICY_SCORE_ONLY:
        return _build_selection(
            selected=raw_score_best,
            policy=selection_policy,
            reason_code="score_only_raw_score_best",
            raw_score_best=raw_score_best,
            baseline_best=baseline_best,
            critical_best=critical_best,
            critical_health_best=critical_health_best,
        )

    if (
        baseline_best is not None
        and critical_health_best is not None
        and _critical_candidate_can_override_raw_score(
            critical_health_best,
            raw_score_best,
            graph_overdue_tolerance_count=graph_overdue_tolerance_count,
            graph_tardiness_tolerance_ratio=graph_tardiness_tolerance_ratio,
        )
    ):
        return _build_selection(
            selected=critical_health_best,
            policy=selection_policy,
            reason_code="balanced_critical_health_better",
            raw_score_best=raw_score_best,
            baseline_best=baseline_best,
            critical_best=critical_best,
            critical_health_best=critical_health_best,
        )

    return _build_selection(
        selected=raw_score_best,
        policy=selection_policy,
        reason_code="balanced_raw_score_best",
        raw_score_best=raw_score_best,
        baseline_best=baseline_best,
        critical_best=critical_best,
        critical_health_best=critical_health_best,
    )


def _normalize_policy(policy: str) -> str:
    value = str(policy or "").strip().lower()
    if value not in _SUPPORTED_POLICIES:
        supported = " / ".join(_SUPPORTED_POLICIES)
        raise ValidationError(f"自动选结果方式只支持 {supported}。", field="candidate_selection_policy")
    return value


def _completed_candidates(candidates: Sequence[Any]) -> List[Any]:
    out = []
    for candidate in candidates or ():
        if str(getattr(candidate, "status", "") or "").strip().lower() != "completed":
            continue
        score = getattr(candidate, "score", None)
        if not score:
            raise ValidationError("已算成功的试算方案缺少评分，无法自动选结果。", field="candidate_score")
        out.append(candidate)
    return out


def _candidate_sort_key(candidate: Any) -> Tuple[Tuple[float, ...], int, int]:
    return (
        _score(candidate),
        0 if str(getattr(candidate, "kind", "")) == CANDIDATE_KIND_BASELINE else 1,
        int(getattr(candidate, "sequence", 0) or 0),
    )


def _score(candidate: Any) -> Tuple[float, ...]:
    return tuple(float(item) for item in tuple(candidate.score))


def _best_of_kind(candidates: Sequence[Any], kind: str) -> Optional[Any]:
    scoped = [candidate for candidate in candidates if str(getattr(candidate, "kind", "")) == kind]
    if not scoped:
        return None
    return min(scoped, key=_candidate_sort_key)


def _health_eligible_critical_best(candidate: Optional[Any]) -> Optional[Any]:
    return (
        candidate
        if candidate is not None and _health_state(getattr(candidate, "health", None)) == HEALTH_BETTER
        else None
    )


def _health_state(health: Any) -> str:
    if isinstance(health, dict):
        return str(health.get("state") or "")
    return str(getattr(health, "state", "") or "")


def _critical_candidate_can_override_raw_score(
    critical: Any,
    raw_score_best: Any,
    *,
    graph_overdue_tolerance_count: int,
    graph_tardiness_tolerance_ratio: float,
) -> bool:
    return (
        _failed_ops(critical) <= _failed_ops(raw_score_best)
        and _metric(critical, "overdue_count")
        <= _metric(raw_score_best, "overdue_count") + int(graph_overdue_tolerance_count)
        and _metric(critical, "total_tardiness_hours")
        <= _metric(raw_score_best, "total_tardiness_hours") * (1.0 + float(graph_tardiness_tolerance_ratio))
    )


def _failed_ops(candidate: Any) -> float:
    return float(_score(candidate)[0])


def _metric(candidate: Any, name: str) -> float:
    metrics = getattr(candidate, "metrics", None)
    if metrics is None or not hasattr(metrics, name):
        raise ValidationError("试算方案缺少必要指标，无法自动选结果。", field=name)
    return float(getattr(metrics, name))


def _build_selection(
    *,
    selected: Any,
    policy: str,
    reason_code: str,
    raw_score_best: Any,
    baseline_best: Optional[Any],
    critical_best: Optional[Any],
    critical_health_best: Optional[Any],
) -> CandidateSelectionResult:
    return CandidateSelectionResult(
        selected_candidate_key=str(selected.candidate_key),
        selected_kind=str(selected.kind),
        selection_policy=policy,
        reason_code=reason_code,
        raw_score_best_key=str(raw_score_best.candidate_key),
        baseline_best_key=_candidate_key_or_none(baseline_best),
        critical_best_key=_candidate_key_or_none(critical_best),
        critical_health_best_key=_candidate_key_or_none(critical_health_best),
        selected_score=_score(selected),
        selected_plan=selected,
    )


def _candidate_key_or_none(candidate: Optional[Any]) -> Optional[str]:
    if candidate is None:
        return None
    return str(candidate.candidate_key)


__all__ = [
    "SELECTION_POLICY_BALANCED",
    "SELECTION_POLICY_SCORE_ONLY",
    "CandidateSelectionResult",
    "select_candidate_plan",
]
