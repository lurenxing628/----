from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.errors import ValidationError

from .search_state import append_unique_rejected_attempt

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState


_COMPARISON_METRICS = ("failed_ops", "overdue_count", "weighted_tardiness_hours", "total_tardiness_hours",
                       "makespan_hours", "changeover_count")


def _finite_value(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _comparison_snapshot(candidate: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = (candidate or {}).get("metrics")
    completion = getattr(metrics, "completion", None)
    known = bool(completion is not None and completion.components_known)
    summary = (candidate or {}).get("summary")
    values = {key: _finite_value(getattr(summary if key == "failed_ops" else metrics, key, None))
              for key in _COMPARISON_METRICS}
    if not known:
        values.update({key: None for key in _COMPARISON_METRICS if key != "failed_ops"})
    score = [_finite_value(value) for value in (candidate or {}).get("score", ())]
    if not known:
        score = [score[0] if score else None] + [None for _ in score[1:]]
    counts = {key: getattr(completion, key, None) for key in (
        "expected_operation_count", "missing_operation_count", "unexpected_result_count", "complete_batch_count")}
    counts["incomplete_batch_count"] = len(completion.incomplete_batch_ids) if completion is not None else None
    scope = getattr(completion, "objective_scope", "unknown")
    context = (scope, tuple(completion.incomplete_batch_ids) if completion is not None else None,
               counts["expected_operation_count"])
    return {"metrics": values, "score": score, "completion": counts, "scope": scope,
            "context": context, "known": known}


def attempt_decision_evidence(
    *, candidate: Dict[str, Any], reference: Optional[Dict[str, Any]], accepted: Optional[bool],
    search_report_state: Optional[OptimizationSearchReportState] = None,
    clock: Optional[Callable[[], float]] = None, t_begin: Optional[float] = None,
    verified: bool = True, comparison_kind: str = "incumbent",
) -> Dict[str, Any]:
    """Freeze the actual decision against its then-current reference, independently of representative rank."""
    elapsed = max(int((clock() - t_begin) * 1000), 0) if clock is not None and t_begin is not None else None
    verified = bool(verified)
    current, previous = _comparison_snapshot(candidate), _comparison_snapshot(reference)
    objective_name = getattr(search_report_state, "objective_name", None)
    if not verified:
        state = "unverified"
    elif reference is None:
        state = "no_reference"
    elif not objective_name or not current["known"] or not previous["known"]:
        state = "unavailable"
    elif current["context"] != previous["context"]:
        state = "different_coverage"
    elif (not current["score"] or len(current["score"]) != len(previous["score"])
          or any(value is None for value in current["score"] + previous["score"])):
        state = "unavailable"
    else:
        state = "comparable"
    comparable = state == "comparable"
    deltas = {key: current["metrics"][key] - previous["metrics"][key]
              if current["metrics"][key] is not None and previous["metrics"][key] is not None else None
              for key in _COMPARISON_METRICS} if comparable else None
    return {"elapsed_ms": elapsed, "event_index": None,
            "accepted": accepted, "verified": verified,
            "strict_improved": current["score"] < previous["score"] if comparable else None,
            "comparison": {"kind": comparison_kind if reference is not None else "none", "state": state,
                           "objective_name": objective_name, "objective_scope": current["scope"],
                           "reference_scope": previous["scope"] if reference is not None else None,
                           "reference_score": previous["score"] if reference is not None else None,
                           "reference_metrics": previous["metrics"] if reference is not None else None,
                           "reference_completion": previous["completion"] if reference is not None else None,
                           "metric_deltas": deltas}}


def validation_error_origin(exc: ValidationError) -> Dict[str, Any]:
    return {"type": "ValidationError", "field": getattr(exc, "field", None), "message": str(exc)}


def candidate_tag(strategy_key: str, dispatch_mode: str, dispatch_rule: str) -> str:
    return f"start:{strategy_key}|{dispatch_mode}:{dispatch_rule}"


def append_rejected_start_attempt(
    *,
    attempts: List[Dict[str, Any]],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> Dict[str, Any]:
    attempt = {
        "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
        "strategy": strategy_key,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": validation_error_origin(exc),
    }
    attempts.append(attempt)
    return attempt


def append_rejected_local_attempt(
    *,
    attempts: List[Dict[str, Any]],
    move: str,
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> Dict[str, Any]:
    attempt = {
        "tag": f"local:{move}",
        "strategy": strategy.value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": validation_error_origin(exc),
    }
    append_unique_rejected_attempt(
        attempts,
        attempt,
    )
    return attempt


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
        "origin": {"type": str(reason), "field": str(reason), "message": str(message)},
    }
    append_unique_rejected_attempt(attempts, attempt)
    return attempt


def evaluate_optional_start_candidate(
    *,
    evaluate: Callable[[], Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    primary: Tuple[str, str, str],
    strict_mode: bool,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode) or (strategy_key, dispatch_mode, dispatch_rule) == primary:
            raise
        append_rejected_start_attempt(
            attempts=attempts,
            strategy_key=strategy_key,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error")
        return None


def evaluate_optional_local_candidate(
    *,
    evaluate: Callable[[], Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    move: str,
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    strict_mode: bool,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode):
            raise
        append_rejected_local_attempt(
            attempts=attempts,
            move=move,
            strategy=strategy,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error")
        return None
