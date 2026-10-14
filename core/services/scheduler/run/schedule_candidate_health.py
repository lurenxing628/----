from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

HEALTH_BETTER = "better"
HEALTH_SAME = "same"
HEALTH_WORSE = "worse"
HEALTH_UNAVAILABLE = "unavailable"
HEALTH_RELATIVE_TOLERANCE_RATIO = 0.05
HEALTH_BETTER_MIN_SCORE = 2
HEALTH_WORSE_MAX_SCORE = -2
HEALTH_EVIDENCE_VERSION = "candidate-health-evidence-v1"

_OP_NODE_PREFIX = "op:"


@dataclass(frozen=True)
class CandidateHealth:
    state: str
    score: int
    reason_code: str
    critical_chain_finish_hours_delta: Optional[float]
    critical_chain_wait_hours_delta: Optional[float]
    top_impact_ops_avg_start_hours_delta: Optional[float]
    critical_chain_slack_hours_delta: Optional[float]
    critical_chain_node_count: int
    top_impact_op_count: int
    decision_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        value = {
            "state": self.state,
            "score": int(self.score),
            "reason_code": self.reason_code,
            "critical_chain_finish_hours_delta": self.critical_chain_finish_hours_delta,
            "critical_chain_wait_hours_delta": self.critical_chain_wait_hours_delta,
            "top_impact_ops_avg_start_hours_delta": self.top_impact_ops_avg_start_hours_delta,
            "critical_chain_slack_hours_delta": self.critical_chain_slack_hours_delta,
            "critical_chain_node_count": int(self.critical_chain_node_count),
            "top_impact_op_count": int(self.top_impact_op_count),
        }
        if self.decision_evidence is not None:
            value["decision_evidence"] = self.decision_evidence
        return value


@dataclass(frozen=True)
class _CriticalPathExtraction:
    op_ids: Set[int]
    reason_code: str = "critical_path_unavailable"


def unavailable_health(reason_code: str) -> CandidateHealth:
    return CandidateHealth(
        state=HEALTH_UNAVAILABLE,
        score=0,
        reason_code=reason_code,
        critical_chain_finish_hours_delta=None,
        critical_chain_wait_hours_delta=None,
        top_impact_ops_avg_start_hours_delta=None,
        critical_chain_slack_hours_delta=None,
        critical_chain_node_count=0,
        top_impact_op_count=0,
        decision_evidence={"version": HEALTH_EVIDENCE_VERSION, "state": "unavailable", "reason_code": reason_code,
                           "relative_tolerance_ratio": None, "neutral_tolerance_hours": None,
                           "score_thresholds": None, "components": []},
    )


def evaluate_candidate_health(
    *,
    baseline_results: Sequence[Any],
    candidate_results: Sequence[Any],
    graph_metrics: Optional[Dict[str, Any]],
    neutral_tolerance_hours: float = 0.01,
) -> CandidateHealth:
    critical_path = _critical_path_op_ids(graph_metrics)
    critical_op_ids = critical_path.op_ids
    if not critical_op_ids:
        return unavailable_health(critical_path.reason_code or "critical_path_unavailable")

    baseline_by_op_id = _results_by_op_id(baseline_results)
    candidate_by_op_id = _results_by_op_id(candidate_results)
    if not critical_op_ids.issubset(set(baseline_by_op_id)) or not critical_op_ids.issubset(set(candidate_by_op_id)):
        return unavailable_health("critical_path_result_missing")

    baseline_finish_hours = _finish_hours(baseline_by_op_id, critical_op_ids)
    candidate_finish_hours = _finish_hours(candidate_by_op_id, critical_op_ids)
    finish_delta = candidate_finish_hours - baseline_finish_hours

    baseline_wait_hours = _chain_wait_hours(baseline_by_op_id, critical_op_ids)
    candidate_wait_hours = _chain_wait_hours(candidate_by_op_id, critical_op_ids)
    wait_delta = candidate_wait_hours - baseline_wait_hours
    top_impact_op_ids = _top_impact_op_ids(graph_metrics)
    top_start = _mean_start_values(
        baseline_by_op_id=baseline_by_op_id,
        candidate_by_op_id=candidate_by_op_id,
        op_ids=top_impact_op_ids,
    )
    slack = _critical_slack_values(graph_metrics)
    components = [
        _health_component("critical_chain_finish_hours_delta", "critical_path_span", baseline_finish_hours,
                          candidate_finish_hours, finish_delta,
                          _relative_tolerance_hours(baseline_finish_hours, fallback_hours=neutral_tolerance_hours)),
        _health_component("critical_chain_wait_hours_delta", "critical_path_wait", baseline_wait_hours,
                          candidate_wait_hours, wait_delta,
                          _relative_tolerance_hours(baseline_wait_hours, fallback_hours=neutral_tolerance_hours)),
        _health_component("top_impact_ops_avg_start_hours_delta", "common_origin_mean_start", top_start["reference"],
                          top_start["candidate"], top_start["delta"], neutral_tolerance_hours, origin=top_start["origin"]),
        _health_component("critical_chain_slack_hours_delta", slack["basis"], slack["reference"], slack["candidate"],
                          slack["delta"], neutral_tolerance_hours, improvement="higher"),
    ]
    score = sum(item["contribution"] for item in components)

    if score >= HEALTH_BETTER_MIN_SCORE:
        state = HEALTH_BETTER
    elif score <= HEALTH_WORSE_MAX_SCORE:
        state = HEALTH_WORSE
    else:
        state = HEALTH_SAME

    return CandidateHealth(
        state=state,
        score=int(score),
        reason_code=f"critical_chain_{state}",
        critical_chain_finish_hours_delta=_round_hours(finish_delta),
        critical_chain_wait_hours_delta=_round_hours(wait_delta),
        top_impact_ops_avg_start_hours_delta=_round_hours(top_start["delta"]),
        critical_chain_slack_hours_delta=_round_hours(slack["delta"]),
        critical_chain_node_count=int(len(critical_op_ids)),
        top_impact_op_count=int(len(top_impact_op_ids)),
        decision_evidence={"version": HEALTH_EVIDENCE_VERSION, "state": "complete", "reason_code": f"critical_chain_{state}",
                           "relative_tolerance_ratio": HEALTH_RELATIVE_TOLERANCE_RATIO,
                           "neutral_tolerance_hours": float(neutral_tolerance_hours),
                           "score_thresholds": {"better_min": HEALTH_BETTER_MIN_SCORE, "worse_max": HEALTH_WORSE_MAX_SCORE},
                           "components": components},
    )


def _health_component(key, basis, reference, candidate, delta, tolerance, *, improvement="lower", origin=None):
    score = _smaller_is_better_score if improvement == "lower" else _larger_is_better_score
    return {"key": key, "basis": basis, "reference_value": reference, "candidate_value": candidate,
            "delta_hours": delta, "tolerance_hours": float(tolerance) if delta is not None else None,
            "contribution": score(delta, tolerance) if delta is not None else 0, "improvement": improvement,
            "state": "complete" if delta is not None else "not_applicable", "origin": origin}


def _results_by_op_id(results: Sequence[Any]) -> Dict[int, Any]:
    out: Dict[int, Any] = {}
    for item in results or ():
        op_id = _coerce_op_id(getattr(item, "op_id", None))
        if op_id is not None:
            out[op_id] = item
    return out


def _critical_path_op_ids(graph_metrics: Optional[Dict[str, Any]]) -> _CriticalPathExtraction:
    if not isinstance(graph_metrics, dict):
        return _CriticalPathExtraction(set(), "critical_path_unavailable")
    values = _first_list(
        graph_metrics,
        (
            "critical_path_op_ids",
            "critical_op_ids",
            "critical_path_node_ids",
        ),
    )
    op_ids = _op_id_set(values)
    if op_ids:
        return _CriticalPathExtraction(op_ids, "")
    # Samples are only for page display and diagnosis; they are not complete enough for health decisions.
    if isinstance(graph_metrics.get("critical_path_sample"), (list, tuple)):
        return _CriticalPathExtraction(set(), "critical_path_sample_only")
    return _CriticalPathExtraction(set(), "critical_path_unavailable")


def _top_impact_op_ids(graph_metrics: Optional[Dict[str, Any]]) -> Set[int]:
    if not isinstance(graph_metrics, dict):
        return set()
    return _op_id_set(_first_list(graph_metrics, ("top_impact_op_ids", "impact_op_ids")))


def _first_list(source: Dict[str, Any], keys: Iterable[str]) -> List[Any]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, (list, tuple)):
            return list(value)
    return []


def _op_id_set(values: Iterable[Any]) -> Set[int]:
    out: Set[int] = set()
    for value in values or ():
        op_id = _coerce_op_id(value)
        if op_id is not None:
            out.add(op_id)
    return out


def _coerce_op_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    if text.startswith(_OP_NODE_PREFIX):
        text = text[len(_OP_NODE_PREFIX) :]
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _finish_hours(results_by_op_id: Dict[int, Any], op_ids: Set[int]) -> float:
    ends = [_require_datetime(getattr(results_by_op_id[op_id], "end_time", None)) for op_id in op_ids]
    starts = [_require_datetime(getattr(results_by_op_id[op_id], "start_time", None)) for op_id in op_ids]
    return _hours(max(ends) - min(starts))


def _chain_wait_hours(results_by_op_id: Dict[int, Any], op_ids: Set[int]) -> float:
    ordered = sorted(
        (results_by_op_id[op_id] for op_id in op_ids),
        key=lambda item: _require_datetime(getattr(item, "start_time", None)),
    )
    wait_hours = 0.0
    previous_end: Optional[datetime] = None
    for item in ordered:
        start = _require_datetime(getattr(item, "start_time", None))
        end = _require_datetime(getattr(item, "end_time", None))
        if previous_end is not None and start > previous_end:
            wait_hours += _hours(start - previous_end)
        if previous_end is None or end > previous_end:
            previous_end = end
    return wait_hours


def _mean_start_values(
    *,
    baseline_by_op_id: Dict[int, Any],
    candidate_by_op_id: Dict[int, Any],
    op_ids: Set[int],
) -> Dict[str, Any]:
    comparable = [op_id for op_id in op_ids if op_id in baseline_by_op_id and op_id in candidate_by_op_id]
    if not comparable:
        return {"reference": None, "candidate": None, "delta": None, "origin": None}
    before = [_require_datetime(getattr(baseline_by_op_id[op_id], "start_time", None)) for op_id in comparable]
    after = [_require_datetime(getattr(candidate_by_op_id[op_id], "start_time", None)) for op_id in comparable]
    origin, count = min(before), float(len(comparable))
    # Keep the original mean of pairwise deltas for the scoring boundary. The
    # two mean positions use one origin, so their saved levels remain inspectable.
    return {"reference": sum(_hours(value - origin) for value in before) / count,
            "candidate": sum(_hours(value - origin) for value in after) / count,
            "delta": sum(_hours(second - first) for first, second in zip(before, after)) / count,
            "origin": origin.isoformat()}


def _critical_slack_values(graph_metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    empty = {"reference": None, "candidate": None, "delta": None, "basis": None}
    if not isinstance(graph_metrics, dict):
        return empty
    if "candidate_critical_chain_slack_hours" in graph_metrics and "baseline_critical_chain_slack_hours" in graph_metrics:
        before, after = (float(graph_metrics[key]) for key in ("baseline_critical_chain_slack_hours", "candidate_critical_chain_slack_hours"))
        return {"reference": before, "candidate": after, "delta": after - before, "basis": "saved_slack_levels"}
    if "critical_chain_slack_hours_delta" in graph_metrics:
        return {**empty, "delta": float(graph_metrics["critical_chain_slack_hours_delta"]), "basis": "saved_slack_delta"}
    return empty


def _require_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("关键链健康计算需要 ScheduleResult.start_time/end_time 是 datetime。")
    return value


def _hours(delta: Any) -> float:
    return float(delta.total_seconds()) / 3600.0


def _relative_tolerance_hours(reference_hours: Optional[float], *, fallback_hours: float) -> float:
    if reference_hours is None:
        return float(fallback_hours)
    reference = abs(float(reference_hours))
    if reference <= 0:
        return float(fallback_hours)
    return reference * HEALTH_RELATIVE_TOLERANCE_RATIO


def _smaller_is_better_score(delta: float, tolerance: float) -> int:
    if delta < -float(tolerance):
        return 1
    if delta > float(tolerance):
        return -1
    return 0


def _larger_is_better_score(delta: float, tolerance: float) -> int:
    if delta > float(tolerance):
        return 1
    if delta < -float(tolerance):
        return -1
    return 0


def _round_hours(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(round(float(value), 4))


__all__ = [
    "HEALTH_BETTER",
    "HEALTH_BETTER_MIN_SCORE",
    "HEALTH_RELATIVE_TOLERANCE_RATIO",
    "HEALTH_SAME",
    "HEALTH_UNAVAILABLE",
    "HEALTH_WORSE",
    "HEALTH_WORSE_MAX_SCORE",
    "CandidateHealth",
    "evaluate_candidate_health",
    "unavailable_health",
]
