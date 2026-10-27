from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics
from core.shared.strict_parse import finite_float, is_number

from .search_state import append_unique_rejected_attempt

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState


_COMPARISON_METRICS = ("failed_ops", "overdue_count", "weighted_tardiness_hours", "total_tardiness_hours",
                       "makespan_hours", "changeover_count")
_COMPLETION_COUNTS = ("expected_operation_count", "missing_operation_count", "unexpected_result_count",
                      "complete_batch_count")


def _finite_value(value: Any) -> Optional[float]:
    return value if is_number(value) and finite_float(value) is not None else None


def _comparison_snapshot(candidate: Dict[str, Any]) -> Dict[str, Any]:
    metrics: ScheduleMetrics = candidate["metrics"]
    summary: ScheduleSummary = candidate["summary"]
    completion = metrics.completion
    known = completion.components_known
    values = {
        key: _finite_value(summary.failed_ops if key == "failed_ops" else (getattr(metrics, key) if known else None))
        for key in _COMPARISON_METRICS
    }
    raw_score = candidate["score"]
    if known:
        score = [_finite_value(value) for value in raw_score]
    else:
        score = [_finite_value(raw_score[0]) if raw_score else None] + [None for _ in raw_score[1:]]
    counts = {key: getattr(completion, key) for key in _COMPLETION_COUNTS}
    counts["incomplete_batch_count"] = len(completion.incomplete_batch_ids)
    scope, incomplete_batch_ids = completion.objective_scope, tuple(completion.incomplete_batch_ids)
    context = (scope, incomplete_batch_ids, counts["expected_operation_count"])
    return {"metrics": values, "score": score, "completion": counts, "scope": scope,
            "context": context, "known": known}


def _comparison_state(current: Dict[str, Any], previous: Dict[str, Any], *, verified: bool) -> str:
    if not verified:
        return "unverified"
    if not current["known"] or not previous["known"]:
        return "unavailable"
    if current["context"] != previous["context"]:
        return "different_coverage"
    if (not current["score"] or len(current["score"]) != len(previous["score"])
            or any(value is None for value in current["score"] + previous["score"])):
        return "unavailable"
    return "comparable"


def attempt_decision_evidence(
    *, candidate: Dict[str, Any], reference: Optional[Dict[str, Any]], accepted: bool,
    search_report_state: OptimizationSearchReportState, clock: Callable[[], float], t_begin: float,
    verified: bool = True, comparison_kind: str = "incumbent",
) -> Dict[str, Any]:
    """Freeze the actual decision against its then-current reference, independently of representative rank."""
    elapsed = max(int((clock() - t_begin) * 1000), 0)
    current = _comparison_snapshot(candidate)
    comparison: Dict[str, Any] = {
        "kind": "none", "state": "no_reference" if verified else "unverified",
        "objective_name": search_report_state.objective_name, "objective_scope": current["scope"],
        "reference_scope": None, "reference_score": None, "reference_metrics": None,
        "reference_completion": None, "metric_deltas": None,
    }
    strict_improved = None
    if reference is not None:
        previous = _comparison_snapshot(reference)
        state = _comparison_state(current, previous, verified=verified)
        comparison.update(kind=comparison_kind, state=state, reference_scope=previous["scope"],
                          reference_score=previous["score"], reference_metrics=previous["metrics"],
                          reference_completion=previous["completion"])
        if state == "comparable":
            comparison["metric_deltas"] = {
                key: current["metrics"][key] - previous["metrics"][key]
                if current["metrics"][key] is not None and previous["metrics"][key] is not None else None
                for key in _COMPARISON_METRICS}
            strict_improved = current["score"] < previous["score"]
    return {"elapsed_ms": elapsed, "event_index": None, "accepted": accepted, "verified": verified,
            "strict_improved": strict_improved, "comparison": comparison}


def candidate_tag(strategy_key: str, dispatch_mode: str, dispatch_rule: str) -> str:
    return f"start:{strategy_key}|{dispatch_mode}:{dispatch_rule}"


def append_rejected_reason_attempt(
    *,
    attempts: List[Dict[str, Any]],
    tag: str,
    strategy: str,
    dispatch_mode: str,
    dispatch_rule: str,
    reason: str,
    message: str,
) -> Dict[str, Any]:
    attempt = {
        "tag": tag,
        "strategy": strategy,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": {"type": reason, "field": reason, "message": message},
    }
    append_unique_rejected_attempt(attempts, attempt)
    return attempt

