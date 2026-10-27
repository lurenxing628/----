from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from .optimizer.shared_process import numeric_score
from .schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan

if TYPE_CHECKING:
    from .schedule_candidate_selection import BusinessObjectiveSelectionResult

UNIFIED_GENERATION_VERSION = "unified_search_v1"
ROLE_RECOMMENDED = "recommended"


def is_unified_generation(value: Any) -> bool:
    """Identify the generation policy on stored/public summary dictionaries."""
    return isinstance(value, dict) and value.get("generation_policy_version") == UNIFIED_GENERATION_VERSION


def candidate_score_summary(candidate: CandidatePlan) -> Optional[List[Any]]:
    score = candidate.score
    if score is None:
        return None
    primary = candidate.objective_name or candidate.objective
    scope = candidate.evaluations[primary]["scoring_scope"]
    return numeric_score(score, components_known=scope["components_known"])


def candidate_metrics_summary(candidate: CandidatePlan, *, score: Optional[List[Any]]) -> Dict[str, Any]:
    metrics = candidate.metrics
    out: Dict[str, Any] = {}
    if score and score[0] is not None:
        out["failed_ops"] = int(score[0])
    if metrics is None:
        return out
    metrics_data = metrics.to_dict()
    for key in (
        "overdue_count",
        "total_tardiness_hours",
        "weighted_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ):
        value = metrics_data.get(key)
        if value is not None:
            out[key] = value
    return out


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
    return candidate.origin is not None and bool(candidate.origin.get("graph_ready_profile"))


def _business_candidate_fields(candidate: CandidatePlan) -> Dict[str, Any]:
    return {
        "generation_policy_version": UNIFIED_GENERATION_VERSION,
        "representative_objectives": candidate.representative_objectives,
        "evaluations": candidate.evaluations,
        "origin": candidate.origin,
        "first_found_elapsed_ms": candidate.first_found_elapsed_ms,
        "search_evidence_ref": candidate.search_evidence_ref,
        "elapsed_seconds": {"value": None, "state": "not_applicable", "reason": "shared_run_time"},
    }


def _candidate_dispatch_rule_fields(candidate: CandidatePlan) -> Dict[str, str]:
    """公开视图的派工规则字段：实际采用的规则，以及与之不同时的配置规则。"""
    # The optimizer searches the whole rule pool; say which rule the plan really uses.
    fields: Dict[str, str] = {}
    adopted_rule = candidate.adopted_dispatch_rule
    if adopted_rule:
        fields["adopted_dispatch_rule"] = adopted_rule
        configured_rule = candidate.dispatch_rule
        if configured_rule and configured_rule != adopted_rule:
            fields["configured_dispatch_rule"] = configured_rule
    return fields


def candidate_public_summary(candidate: CandidatePlan, *, roles: List[str]) -> Dict[str, Any]:
    score = candidate_score_summary(candidate)
    # health / elapsed_ms keep the saved public shape: business candidates have no
    # critical-chain health record and share one run time (see elapsed_seconds below).
    summary: Dict[str, Any] = {
        "label": candidate.label,
        "kind": candidate.kind,
        "status": candidate.status,
        "score": score,
        "metrics": candidate_metrics_summary(candidate, score=score),
        "health": None,
        "graph_enabled": candidate_graph_enabled(candidate),
        "critical_weight": candidate.graph_critical_weight,
        "impact_weight": candidate.graph_impact_weight,
        "downstream_weight": candidate.graph_downstream_weight,
        "elapsed_ms": None,
        "detail_saved": ROLE_RECOMMENDED not in roles,
        "roles": roles,
        **_business_candidate_fields(candidate),
    }
    summary.update(_candidate_dispatch_rule_fields(candidate))
    return summary


def candidate_comparison_public_summary(candidate_comparison: CandidateComparisonOutcome) -> Dict[str, Any]:
    selection = cast("BusinessObjectiveSelectionResult", candidate_comparison.selection)
    roles_by_key = candidate_roles_by_key(selection)
    candidates = candidate_comparison.candidates
    return {
        "enabled": True,
        "generation_policy_version": UNIFIED_GENERATION_VERSION,
        "primary_objective": candidate_comparison.primary_objective,
        "target_objectives": list(candidate_comparison.target_objectives),
        "planned_candidate_count": len(candidates),
        "completed_candidate_count": len(candidates),
        "time_budget_reached": candidate_comparison.time_budget_reached,
        "run_time_budget_seconds": candidate_comparison.run_time_budget_seconds,
        "selection_policy_version": selection.selection_policy_version,
        "selection_reason_code": selection.reason_code,
        "selection": selection.to_dict(),
        "unified_process": candidate_comparison.unified_process,
        "candidates": [candidate_public_summary(candidate, roles=roles_by_key.get(candidate.candidate_key, []))
                       for candidate in candidates],
    }


def candidate_comparison_minimal_summary(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    keys = (
        "enabled", "generation_policy_version", "primary_objective", "target_objectives",
        "planned_candidate_count", "completed_candidate_count", "time_budget_reached",
        "run_time_budget_seconds", "selection_policy_version", "selection_reason_code",
    )
    return {key: raw[key] for key in keys if key in raw}


__all__ = [
    "candidate_comparison_minimal_summary",
    "candidate_comparison_public_summary",
    "candidate_graph_enabled",
    "candidate_metrics_summary",
    "candidate_public_summary",
    "candidate_roles_by_key",
    "candidate_score_summary",
    "is_unified_generation",
]
