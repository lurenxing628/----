from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

HEALTH_BETTER = "better"
HEALTH_SAME = "same"
HEALTH_WORSE = "worse"
HEALTH_UNAVAILABLE = "unavailable"

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

    def to_dict(self) -> Dict[str, Any]:
        return {
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
    )


def evaluate_candidate_health(
    *,
    baseline_results: Sequence[Any],
    candidate_results: Sequence[Any],
    graph_metrics: Optional[Dict[str, Any]],
    neutral_tolerance_hours: float = 0.01,
) -> CandidateHealth:
    critical_op_ids = _critical_path_op_ids(graph_metrics)
    if not critical_op_ids:
        return unavailable_health("critical_path_unavailable")

    baseline_by_op_id = _results_by_op_id(baseline_results)
    candidate_by_op_id = _results_by_op_id(candidate_results)
    if not critical_op_ids.issubset(set(baseline_by_op_id)) or not critical_op_ids.issubset(set(candidate_by_op_id)):
        return unavailable_health("critical_path_result_missing")

    finish_delta = _finish_hours(candidate_by_op_id, critical_op_ids) - _finish_hours(baseline_by_op_id, critical_op_ids)
    wait_delta = _chain_wait_hours(candidate_by_op_id, critical_op_ids) - _chain_wait_hours(baseline_by_op_id, critical_op_ids)
    top_impact_op_ids = _top_impact_op_ids(graph_metrics)
    top_start_delta = _avg_start_delta_hours(
        baseline_by_op_id=baseline_by_op_id,
        candidate_by_op_id=candidate_by_op_id,
        op_ids=top_impact_op_ids,
    )
    slack_delta = _critical_slack_delta_hours(graph_metrics)

    score = 0
    score += _smaller_is_better_score(finish_delta, neutral_tolerance_hours)
    score += _smaller_is_better_score(wait_delta, neutral_tolerance_hours)
    if top_start_delta is not None:
        score += _smaller_is_better_score(top_start_delta, neutral_tolerance_hours)
    if slack_delta is not None:
        score += _larger_is_better_score(slack_delta, neutral_tolerance_hours)

    if score > 0:
        state = HEALTH_BETTER
    elif score < 0:
        state = HEALTH_WORSE
    else:
        state = HEALTH_SAME

    return CandidateHealth(
        state=state,
        score=int(score),
        reason_code=f"critical_chain_{state}",
        critical_chain_finish_hours_delta=_round_hours(finish_delta),
        critical_chain_wait_hours_delta=_round_hours(wait_delta),
        top_impact_ops_avg_start_hours_delta=_round_hours(top_start_delta),
        critical_chain_slack_hours_delta=_round_hours(slack_delta),
        critical_chain_node_count=int(len(critical_op_ids)),
        top_impact_op_count=int(len(top_impact_op_ids)),
    )


def _results_by_op_id(results: Sequence[Any]) -> Dict[int, Any]:
    out: Dict[int, Any] = {}
    for item in results or ():
        op_id = _coerce_op_id(getattr(item, "op_id", None))
        if op_id is not None:
            out[op_id] = item
    return out


def _critical_path_op_ids(graph_metrics: Optional[Dict[str, Any]]) -> Set[int]:
    if not isinstance(graph_metrics, dict):
        return set()
    values = _first_list(
        graph_metrics,
        (
            "critical_path_op_ids",
            "critical_op_ids",
            "critical_path_sample",
            "critical_path",
            "critical_path_node_ids",
        ),
    )
    return _op_id_set(values)


def _top_impact_op_ids(graph_metrics: Optional[Dict[str, Any]]) -> Set[int]:
    if not isinstance(graph_metrics, dict):
        return set()
    direct = _op_id_set(_first_list(graph_metrics, ("top_impact_op_ids", "impact_op_ids")))
    if direct:
        return direct

    scored = _impact_scored_op_ids(graph_metrics.get("graph_score_sample"), allow_node_id=False)
    if scored:
        return _positive_impact_op_ids(scored)

    node_metrics = _impact_scored_op_ids(graph_metrics.get("node_metrics_sample"), allow_node_id=True)
    return _positive_impact_op_ids(node_metrics)


def _impact_scored_op_ids(sample: Any, *, allow_node_id: bool) -> List[Tuple[int, int]]:
    scored: List[Tuple[int, int]] = []
    for item in list(sample or ()):
        if not isinstance(item, dict):
            continue
        op_id = _impact_sample_op_id(item, allow_node_id=allow_node_id)
        if op_id is None:
            continue
        scored.append((int(item.get("impact_count") or 0), op_id))
    scored.sort(reverse=True)
    return scored


def _impact_sample_op_id(item: Dict[str, Any], *, allow_node_id: bool) -> Optional[int]:
    if allow_node_id:
        return _coerce_op_id(item.get("op_id") if "op_id" in item else item.get("node_id"))
    return _coerce_op_id(item.get("op_id"))


def _positive_impact_op_ids(scored_op_ids: List[Tuple[int, int]]) -> Set[int]:
    return {op_id for impact_count, op_id in scored_op_ids if impact_count > 0}


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


def _avg_start_delta_hours(
    *,
    baseline_by_op_id: Dict[int, Any],
    candidate_by_op_id: Dict[int, Any],
    op_ids: Set[int],
) -> Optional[float]:
    comparable = [op_id for op_id in op_ids if op_id in baseline_by_op_id and op_id in candidate_by_op_id]
    if not comparable:
        return None
    deltas = [
        _hours(
            _require_datetime(getattr(candidate_by_op_id[op_id], "start_time", None))
            - _require_datetime(getattr(baseline_by_op_id[op_id], "start_time", None))
        )
        for op_id in comparable
    ]
    return sum(deltas) / float(len(deltas))


def _critical_slack_delta_hours(graph_metrics: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(graph_metrics, dict):
        return None
    if "candidate_critical_chain_slack_hours" in graph_metrics and "baseline_critical_chain_slack_hours" in graph_metrics:
        return float(graph_metrics["candidate_critical_chain_slack_hours"]) - float(
            graph_metrics["baseline_critical_chain_slack_hours"]
        )
    if "critical_chain_slack_hours_delta" in graph_metrics:
        return float(graph_metrics["critical_chain_slack_hours_delta"])
    return None


def _require_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("关键链健康计算需要 ScheduleResult.start_time/end_time 是 datetime。")
    return value


def _hours(delta: Any) -> float:
    return float(delta.total_seconds()) / 3600.0


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
    "HEALTH_SAME",
    "HEALTH_UNAVAILABLE",
    "HEALTH_WORSE",
    "CandidateHealth",
    "evaluate_candidate_health",
    "unavailable_health",
]
