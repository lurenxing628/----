from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from .optimizer.shared_process import numeric_score
from .schedule_candidate_plan import BUSINESS_FIELDS, GRAPH_PROFILE_FIELD, CandidateComparisonOutcome, CandidatePlan

if TYPE_CHECKING:
    from .schedule_candidate_selection import BusinessObjectiveSelectionResult

ROLE_RECOMMENDED = "recommended"


def candidate_score_summary(candidate: CandidatePlan) -> List[Any]:
    primary = candidate.objective_name
    score = candidate.score
    scope = candidate.evaluations[primary]["scoring_scope"]
    return numeric_score(score, components_known=scope["components_known"])


def candidate_metrics_summary(candidate: CandidatePlan) -> Dict[str, Any]:
    metrics_data = candidate.metrics.numeric_dict()
    return {
        "failed_ops": int(candidate.score[0]),
        "overdue_count": metrics_data["overdue_count"],
        "total_tardiness_hours": metrics_data["total_tardiness_hours"],
        "weighted_tardiness_hours": metrics_data["weighted_tardiness_hours"],
        "makespan_hours": metrics_data["makespan_hours"],
        "changeover_count": metrics_data["changeover_count"],
    }


def candidate_roles_by_key(selection: BusinessObjectiveSelectionResult) -> Dict[str, List[str]]:
    roles: Dict[str, List[str]] = {}

    def add(key: Optional[str], role: str) -> None:
        if key is None:
            return
        roles.setdefault(key, [])
        if role not in roles[key]:
            roles[key].append(role)

    add(selection.selected_candidate_key, ROLE_RECOMMENDED)
    for objective, key in selection.objective_winners.items():
        add(key, objective)
    return roles


def candidate_graph_enabled(candidate: CandidatePlan) -> bool:
    return bool(candidate.origin.get(GRAPH_PROFILE_FIELD))


def candidate_public_summary(candidate: CandidatePlan, *, roles: List[str]) -> Dict[str, Any]:
    """One receipt-summary candidate: its own keys and the BUSINESS_FIELDS the stored artifact also carries."""
    return {
        "label": candidate.label,
        "score": candidate_score_summary(candidate),
        "metrics": candidate_metrics_summary(candidate),
        "graph_enabled": candidate_graph_enabled(candidate),
        "detail_saved": ROLE_RECOMMENDED not in roles,
        "roles": roles,
        **{name: getattr(candidate, name) for name in BUSINESS_FIELDS},
        "adopted_dispatch_rule": candidate.used_params["dispatch_rule"],
    }


def candidate_comparison_public_summary(candidate_comparison: CandidateComparisonOutcome) -> Dict[str, Any]:
    selection = cast("BusinessObjectiveSelectionResult", candidate_comparison.selection)
    roles_by_key = candidate_roles_by_key(selection)
    candidates = candidate_comparison.candidates
    return {
        "primary_objective": candidate_comparison.primary_objective,
        "target_objectives": list(candidate_comparison.target_objectives),
        "time_budget_reached": candidate_comparison.time_budget_reached,
        "run_time_budget_seconds": candidate_comparison.run_time_budget_seconds,
        "selection_reason_code": selection.reason_code,
        "selection": selection.to_dict(),
        "candidates": [candidate_public_summary(candidate, roles=roles_by_key.get(candidate.candidate_key, []))
                       for candidate in candidates],
    }


__all__ = [
    "candidate_comparison_public_summary",
    "candidate_graph_enabled",
    "candidate_metrics_summary",
    "candidate_public_summary",
    "candidate_roles_by_key",
    "candidate_score_summary",
]
