from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithms import SortStrategy

from .attempt_records import append_rejected_reason_attempt, attempt_decision_evidence, candidate_tag

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState


def _append_ortools_attempt(
    *, attempts: List[Dict[str, Any]], candidate: Dict[str, Any],
    decision_evidence: Optional[Dict[str, Any]] = None,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    attempt = {
        "tag": f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}",
        "source": "ortools_warmstart",
        "strategy": candidate["strategy"].value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "used_params": dict(candidate["params"]),
        "score": list(candidate["score"]),
        "failed_ops": candidate["summary"].failed_ops,
        "metrics": metrics.to_dict(),
        "algo_stats": candidate["algo_stats"],
    }
    if decision_evidence is not None:
        attempt.update(decision_evidence)
    attempts.append(attempt)


def _append_ortools_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    now: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    improvement_trace.append(
        {
            "elapsed_ms": int((now() - t_begin) * 1000),
            "tag": f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}",
            "strategy": candidate["strategy"].value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(candidate["score"]),
            "metrics": metrics.to_dict(),
        }
    )


def _mark_report_phase_skipped(search_report_state: Optional[OptimizationSearchReportState], phase: str, reason: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(phase, reason)


def _mark_report_deadline_skip(search_report_state: Optional[OptimizationSearchReportState], phase: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()
        search_report_state.mark_phase_skipped(phase, "time_budget")


def _record_ortools_optional_failure(
    *,
    attempts: List[Dict[str, Any]],
    strategy: SortStrategy,
    dispatch_mode: str,
    dispatch_rule: str,
    search_report_state: Optional[OptimizationSearchReportState],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    scheduler: Any,
    logger: Any,
    exc: Exception,
) -> None:
    append_rejected_reason_attempt(
        attempts=attempts,
        tag=f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}",
        strategy=strategy.value,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        reason="optional_warmstart_failed",
        message=str(exc),
    )
    if search_report_state is not None:
        search_report_state.mark_optional_warmstart_failed()
    increment_counter(optimizer_algo_stats if isinstance(optimizer_algo_stats, dict) else scheduler, "ortools_warmstart_failed_count")
    if not logger:
        return
    try:
        logger.warning(f"OR-Tools 预热失败（已忽略）：{exc}", exc_info=True)
    except TypeError:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=10))
        logger.warning(f"OR-Tools 预热失败（已忽略）：{exc}\n{tb}")


def _record_ortools_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    now: Callable[[], float],
    t_begin: float,
) -> Optional[Dict[str, Any]]:
    fingerprint = None
    if search_report_state is not None:
        fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin="ortools_warmstart")
    accepted = not (best is not None and candidate["score"] >= best["score"])
    _append_ortools_attempt(
        attempts=attempts, candidate=candidate,
        decision_evidence=attempt_decision_evidence(
            candidate=candidate, reference=best, accepted=accepted,
            search_report_state=search_report_state, clock=now, t_begin=t_begin,
        ),
    )
    if not accepted:
        return best
    if search_report_state is not None:
        search_report_state.mark_candidate_accepted(candidate, origin="ortools_warmstart", fingerprint=fingerprint)
    _append_ortools_trace(improvement_trace=improvement_trace, candidate=candidate, now=now, t_begin=t_begin)
    return candidate


def _multi_start_deadline_reached(
    *, now: Callable[[], float], deadline: float, search_report_state: Optional[OptimizationSearchReportState],
) -> bool:
    current = now()
    if current >= deadline:
        if search_report_state is not None:
            search_report_state.mark_deadline_reached()
        return True
    return False


def _append_multi_start_attempt(
    *,
    attempts: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    decision_evidence: Optional[Dict[str, Any]] = None,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    attempt = {
        "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
        "source": "multi_start",
        "strategy": candidate["strategy"].value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "used_params": dict(candidate["params"]),
        "score": list(candidate["score"]),
        "failed_ops": candidate["summary"].failed_ops,
        "metrics": metrics.to_dict(),
        "algo_stats": candidate["algo_stats"],
    }
    if decision_evidence is not None:
        attempt.update(decision_evidence)
    attempts.append(attempt)


def _append_multi_start_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    now: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    improvement_trace.append(
        {
            "elapsed_ms": int((now() - t_begin) * 1000),
            "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
            "strategy": candidate["strategy"].value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(candidate["score"]),
            "metrics": metrics.to_dict(),
        }
    )


def _record_multi_start_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    now: Callable[[], float],
    t_begin: float,
) -> Optional[Dict[str, Any]]:
    fingerprint = None
    if search_report_state is not None:
        fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin="multi_start")
    accepted = not (best is not None and candidate["score"] >= best["score"])
    _append_multi_start_attempt(
        attempts=attempts,
        candidate=candidate,
        strategy_key=strategy_key,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        decision_evidence=attempt_decision_evidence(
            candidate=candidate, reference=best, accepted=accepted,
            search_report_state=search_report_state, clock=now, t_begin=t_begin,
        ),
    )
    if not accepted:
        return best
    if search_report_state is not None:
        search_report_state.mark_candidate_accepted(candidate, origin="multi_start", fingerprint=fingerprint)
    _append_multi_start_trace(
        improvement_trace=improvement_trace,
        candidate=candidate,
        strategy_key=strategy_key,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        now=now,
        t_begin=t_begin,
    )
    return candidate


__all__ = [
    "_mark_report_deadline_skip",
    "_mark_report_phase_skipped",
    "_multi_start_deadline_reached",
    "_record_multi_start_candidate",
    "_record_ortools_candidate",
    "_record_ortools_optional_failure",
]
