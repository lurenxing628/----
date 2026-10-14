from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.errors import ValidationError

from .schedule_candidate_health import HEALTH_BETTER
from .schedule_candidate_specs import CANDIDATE_KIND_BASELINE, CANDIDATE_KIND_CRITICAL_CHAIN

SELECTION_POLICY_SCORE_ONLY = "score_only"
SELECTION_POLICY_BALANCED = "balanced"

_SUPPORTED_POLICIES = (SELECTION_POLICY_SCORE_ONLY, SELECTION_POLICY_BALANCED)
SELECTION_EVIDENCE_VERSION = "candidate-selection-evidence-v1"


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
    selection_policy_version: str = "candidate-selection-v1"
    overdue_tolerance_count: Optional[int] = None
    tardiness_tolerance_ratio: Optional[float] = None
    decision_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        value = {
            "selected_candidate_key": self.selected_candidate_key,
            "selected_kind": self.selected_kind,
            "selection_policy": self.selection_policy,
            "reason_code": self.reason_code,
            "raw_score_best_key": self.raw_score_best_key,
            "baseline_best_key": self.baseline_best_key,
            "critical_best_key": self.critical_best_key,
            "critical_health_best_key": self.critical_health_best_key,
            "selected_score": list(self.selected_score),
            "selection_policy_version": self.selection_policy_version,
            "overdue_tolerance_count": self.overdue_tolerance_count,
            "tardiness_tolerance_ratio": self.tardiness_tolerance_ratio,
        }
        if self.decision_evidence is not None:
            value["decision_evidence"] = self.decision_evidence
        return value


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
    balanced = _balanced_assessment(selection_policy, baseline_best, critical_best, raw_score_best,
                                    graph_overdue_tolerance_count, graph_tardiness_tolerance_ratio)
    selected: Any
    if selection_policy == SELECTION_POLICY_SCORE_ONLY:
        selected, reason = raw_score_best, "score_only_raw_score_best"
    elif balanced["accepted"]:
        selected, reason = critical_health_best, "balanced_critical_health_better"
    else:
        selected, reason = raw_score_best, "balanced_raw_score_best"
    balanced["override_applied"] = selected.candidate_key != raw_score_best.candidate_key
    return _build_selection(
        selected=selected,
        policy=selection_policy,
        reason_code=reason,
        raw_score_best=raw_score_best,
        baseline_best=baseline_best,
        critical_best=critical_best,
        critical_health_best=critical_health_best,
        overdue_tolerance_count=graph_overdue_tolerance_count if selection_policy == SELECTION_POLICY_BALANCED else None,
        tardiness_tolerance_ratio=graph_tardiness_tolerance_ratio if selection_policy == SELECTION_POLICY_BALANCED else None,
        decision_evidence={"version": SELECTION_EVIDENCE_VERSION, "state": "complete",
                           "anchors": {"raw_score_best": _candidate_snapshot(raw_score_best),
                                       "health_reference": _candidate_snapshot(baseline_best)},
                           "selected": _candidate_snapshot(selected),
                           "tiebreak": _tiebreak_evidence(completed, raw_score_best), "balanced_checks": balanced},
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
        if len(_score(candidate)) < 2:
            raise ValidationError("试算方案评分缺少主目标分数，无法自动选结果。", field="candidate_score")
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


def _critical_candidate_checks(
    critical: Any,
    raw_score_best: Any,
    *,
    graph_overdue_tolerance_count: int,
    graph_tardiness_tolerance_ratio: float,
) -> List[Dict[str, Any]]:
    values = (
        ("failed_ops", _failed_ops(critical), _failed_ops(raw_score_best), None),
        ("objective_primary_score", _objective_primary_score(critical), _objective_primary_score(raw_score_best), None),
        ("overdue_count", _metric(critical, "overdue_count"), _metric(raw_score_best, "overdue_count"), int(graph_overdue_tolerance_count)),
        ("total_tardiness_hours", _metric(critical, "total_tardiness_hours"), _metric(raw_score_best, "total_tardiness_hours"), float(graph_tardiness_tolerance_ratio)),
    )
    result = []
    for key, value, reference, tolerance in values:
        limit = (reference if tolerance is None else reference + tolerance if key == "overdue_count"
                 else reference * (1.0 + tolerance))
        result.append({"key": key, "candidate_value": value, "reference_value": reference,
                       "limit": limit, "passed": value <= limit, "tolerance": tolerance})
    return result


def _balanced_assessment(policy, baseline, critical, raw, count_tolerance, ratio_tolerance):
    reason = ("score_only" if policy == SELECTION_POLICY_SCORE_ONLY else "baseline_unavailable" if baseline is None else
              "critical_candidate_unavailable" if critical is None else
              "critical_health_not_better" if _health_state(getattr(critical, "health", None)) != HEALTH_BETTER else None)
    result = {"eligible": reason is None, "checked": reason is None, "reason_code": reason,
              "candidate_key": _candidate_key_or_none(critical), "reference_candidate_key": _candidate_key_or_none(raw),
              "health_reference_candidate_key": _candidate_key_or_none(baseline),
              "health_state": _health_state(getattr(critical, "health", None)) or None,
              "checks": [], "accepted": False, "override_applied": False}
    if reason is None:
        result["checks"] = _critical_candidate_checks(critical, raw, graph_overdue_tolerance_count=count_tolerance,
                                                      graph_tardiness_tolerance_ratio=ratio_tolerance)
        result["accepted"] = all(item["passed"] for item in result["checks"])
    return result


def _candidate_snapshot(candidate):
    if candidate is None:
        return None
    metrics = getattr(candidate, "metrics", None)
    return {"candidate_key": str(candidate.candidate_key), "score": list(_score(candidate)),
            "failed_ops": _failed_ops(candidate), "primary_score": _objective_primary_score(candidate),
            **{key: float(getattr(metrics, key)) if metrics is not None and hasattr(metrics, key) else None
               for key in ("overdue_count", "total_tardiness_hours")}}


def _tiebreak_evidence(candidates, raw):
    ordered = sorted(candidates, key=_candidate_sort_key)
    runner_up = ordered[1] if len(ordered) > 1 else None
    step, index = _decisive_score_step(raw, runner_up)
    return {"rule": "full_score_baseline_sequence_v1", "raw_score_best_candidate_key": str(raw.candidate_key),
            "runner_up_candidate_key": _candidate_key_or_none(runner_up), "decisive_step": step,
            "decisive_score_index": index,
            "primary_tied_candidate_keys": [str(row.candidate_key) for row in ordered if _objective_primary_score(row) == _objective_primary_score(raw)],
            "full_score_tied_candidate_keys": [str(row.candidate_key) for row in ordered if _score(row) == _score(raw)]}


def _decisive_score_step(winner, runner_up):
    if runner_up is None:
        return "only_completed_candidate", None
    before, after = _score(winner), _score(runner_up)
    for index, (first, second) in enumerate(zip(before, after)):
        if first != second:
            return ("failed_ops" if index == 0 else "primary_score" if index == 1 else "secondary_score"), index
    if len(before) != len(after):
        return "score_length", None
    first, second = _candidate_sort_key(winner), _candidate_sort_key(runner_up)
    if first[1] != second[1]:
        return "baseline_preference", None
    return ("candidate_sequence" if first[2] != second[2] else "input_order"), None


def _failed_ops(candidate: Any) -> float:
    return float(_score(candidate)[0])


def _objective_primary_score(candidate: Any) -> float:
    score = _score(candidate)
    if len(score) < 2:
        raise ValidationError("试算方案评分缺少主目标分数，无法自动选结果。", field="candidate_score")
    return float(score[1])


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
    overdue_tolerance_count: Optional[int],
    tardiness_tolerance_ratio: Optional[float],
    decision_evidence: Dict[str, Any],
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
        overdue_tolerance_count=int(overdue_tolerance_count) if overdue_tolerance_count is not None else None,
        tardiness_tolerance_ratio=float(tardiness_tolerance_ratio) if tardiness_tolerance_ratio is not None else None,
        decision_evidence=decision_evidence,
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
