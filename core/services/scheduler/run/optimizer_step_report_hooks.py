from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import increment_counter

from .optimizer_attempt_records import append_rejected_reason_attempt, candidate_tag

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


def _append_ortools_attempt(*, attempts: List[Dict[str, Any]], candidate: Dict[str, Any]) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    attempts.append(
        {
            "tag": f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}",
            "strategy": candidate["strategy"].value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "used_params": dict(candidate["params"] or {}),
            "score": list(candidate["score"]),
            "failed_ops": int(candidate["summary"].failed_ops),
            "metrics": metrics.to_dict(),
            "algo_stats": candidate["algo_stats"],
        }
    )


def _append_ortools_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    now: Callable[[], float],
    t_begin: float,
) -> None:
    if len(improvement_trace) >= 200:
        return
    metrics = candidate["metrics"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
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


def _record_ortools_failure(*, optimizer_algo_stats: Optional[Dict[str, Any]], scheduler: Any, logger: Any, exc: Exception) -> None:
    increment_counter(optimizer_algo_stats if isinstance(optimizer_algo_stats, dict) else scheduler, "ortools_warmstart_failed_count")
    if not logger:
        return
    tb = traceback.format_exc(limit=10)
    try:
        logger.warning(f"OR-Tools 预热失败（已忽略）：{exc}", exc_info=True)
    except TypeError:
        logger.warning(f"OR-Tools 预热失败（已忽略）：{exc}\n{tb}")


def _record_ortools_rejection_attempt(
    *,
    attempts: List[Dict[str, Any]],
    strategy: SortStrategy,
    dispatch_mode: str,
    dispatch_rule: str,
    reason: str,
    message: str,
) -> Dict[str, Any]:
    return append_rejected_reason_attempt(
        attempts=attempts,
        tag=f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}",
        strategy=strategy.value,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        reason=reason,
        message=message,
    )


def _mark_report_phase_skipped(search_report_state: Optional[OptimizationSearchReportState], phase: str, reason: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(phase, reason)


def _mark_report_deadline(search_report_state: Optional[OptimizationSearchReportState]) -> None:
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()


def _mark_report_deadline_skip(search_report_state: Optional[OptimizationSearchReportState], phase: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()
        search_report_state.mark_phase_skipped(phase, "time_budget")


def _mark_report_evaluated(search_report_state: Optional[OptimizationSearchReportState], candidate: Dict[str, Any], origin: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_candidate_evaluated(candidate, origin=origin)


def _mark_report_accepted(search_report_state: Optional[OptimizationSearchReportState], candidate: Dict[str, Any], origin: str) -> None:
    if search_report_state is not None:
        search_report_state.mark_candidate_accepted(candidate, origin=origin)


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
    _record_ortools_rejection_attempt(
        attempts=attempts,
        strategy=strategy,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        reason="optional_warmstart_failed",
        message=str(exc),
    )
    if search_report_state is not None:
        search_report_state.mark_optional_warmstart_failed(reason="optional_warmstart_failed")
    _record_ortools_failure(optimizer_algo_stats=optimizer_algo_stats, scheduler=scheduler, logger=logger, exc=exc)


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
    _mark_report_evaluated(search_report_state, candidate, "ortools_warmstart")
    _append_ortools_attempt(attempts=attempts, candidate=candidate)
    if best is not None and candidate["score"] >= best["score"]:
        return best
    _mark_report_accepted(search_report_state, candidate, "ortools_warmstart")
    _append_ortools_trace(improvement_trace=improvement_trace, candidate=candidate, now=now, t_begin=t_begin)
    return candidate


def _multi_start_deadline_reached(*, now: Callable[[], float], deadline: float, search_report_state: Optional[OptimizationSearchReportState]) -> bool:
    if now() <= deadline:
        return False
    _mark_report_deadline(search_report_state)
    return True


def _append_multi_start_attempt(
    *,
    attempts: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
) -> None:
    metrics = candidate["metrics"]
    attempts.append(
        {
            "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
            "strategy": candidate["strategy"].value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "used_params": dict(candidate["params"] or {}),
            "score": list(candidate["score"]),
            "failed_ops": int(candidate["summary"].failed_ops),
            "metrics": metrics.to_dict(),
            "algo_stats": candidate["algo_stats"],
        }
    )


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
    if len(improvement_trace) >= 200:
        return
    metrics = candidate["metrics"]
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
    _mark_report_evaluated(search_report_state, candidate, "multi_start")
    _append_multi_start_attempt(
        attempts=attempts,
        candidate=candidate,
        strategy_key=strategy_key,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
    )
    if best is not None and candidate["score"] >= best["score"]:
        return best
    _mark_report_accepted(search_report_state, candidate, "multi_start")
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
