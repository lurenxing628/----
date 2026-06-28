from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from .optimizer_acceptance import AcceptanceDecision

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


def mark_current_candidate_accepted(
    *,
    search_report_state: Optional[OptimizationSearchReportState],
    candidate: Optional[Dict[str, Any]],
    acceptance_decision: AcceptanceDecision,
) -> None:
    if candidate is None or search_report_state is None:
        return
    search_report_state.mark_current_candidate_accepted(
        candidate,
        origin="local_search",
        acceptance_event=acceptance_decision.to_report_dict(),
    )


def mark_best_candidate_accepted(
    *,
    search_report_state: Optional[OptimizationSearchReportState],
    candidate: Optional[Dict[str, Any]],
    acceptance_decision: AcceptanceDecision,
) -> None:
    if candidate is None or search_report_state is None:
        return
    search_report_state.local_search_improved = True
    search_report_state.mark_candidate_accepted(
        candidate,
        origin="local_search",
        acceptance_event=acceptance_decision.to_report_dict(),
    )


def mark_acceptance_rejected(
    *,
    search_report_state: Optional[OptimizationSearchReportState],
    acceptance_decision: AcceptanceDecision,
) -> None:
    if search_report_state is None:
        return
    search_report_state.mark_acceptance_event(
        acceptance_decision.to_report_dict(),
        best_improved=False,
        current_accepted=False,
    )


__all__ = [
    "mark_acceptance_rejected",
    "mark_best_candidate_accepted",
    "mark_current_candidate_accepted",
]
