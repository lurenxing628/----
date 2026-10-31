from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from core.algorithm_runtime.algo_stats import increment_counter

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState


def _record_ortools_optional_failure(
    *,
    optimizer_algo_stats: Dict[str, Any],
) -> None:
    increment_counter(optimizer_algo_stats, "ortools_warmstart_failed_count")


def _record_ortools_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    search_report_state: OptimizationSearchReportState,
) -> Optional[Dict[str, Any]]:
    fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin="ortools_warmstart")
    accepted = not (best is not None and candidate["score"] >= best["score"])
    if not accepted:
        return best
    search_report_state.mark_candidate_accepted(candidate, origin="ortools_warmstart", fingerprint=fingerprint)
    return candidate


def _record_multi_start_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    search_report_state: OptimizationSearchReportState,
) -> Optional[Dict[str, Any]]:
    fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin="multi_start")
    accepted = not (best is not None and candidate["score"] >= best["score"])
    if not accepted:
        return best
    search_report_state.mark_candidate_accepted(candidate, origin="multi_start", fingerprint=fingerprint)
    return candidate


__all__ = [
    "_record_multi_start_candidate",
    "_record_ortools_candidate",
    "_record_ortools_optional_failure",
]
