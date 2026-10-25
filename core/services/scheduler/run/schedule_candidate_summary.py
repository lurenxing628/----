from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from core.models.schedule_plan_role import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST

from .optimizer.shared_process import numeric_score
from .schedule_candidate_plan import (
    CANDIDATE_KIND_CRITICAL_CHAIN,
    UNCERTIFIED,
    UNCERTIFIED_PREFIX,
    CandidateComparisonOutcome,
    CandidatePlan,
)

if TYPE_CHECKING:
    from .schedule_candidate_selection import BusinessObjectiveSelectionResult

UNIFIED_GENERATION_VERSION = "unified_search_v1"
ROLE_RECOMMENDED = "recommended"

_PUBLIC_FAILURE_REASON_CODES = {
    "candidate_failed",
    "candidate_time_budget_reached",
}


def is_unified_generation(value: Any) -> bool:
    """Identify the generation policy on stored/public summary dictionaries."""
    return isinstance(value, dict) and value.get("generation_policy_version") == UNIFIED_GENERATION_VERSION


def candidate_score_summary(candidate: CandidatePlan) -> Optional[List[Any]]:
    score = candidate.score
    if score is None:
        return None
    if candidate.generation_policy_version == UNIFIED_GENERATION_VERSION:
        primary = candidate.objective_name or candidate.objective
        scope = candidate.evaluations[primary]["scoring_scope"]
        return numeric_score(score, components_known=scope["components_known"])
    return [float(item) for item in score]


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


def candidate_health_summary(candidate: CandidatePlan) -> Optional[Dict[str, Any]]:
    if candidate.generation_policy_version == UNIFIED_GENERATION_VERSION:
        return None
    raw = candidate.health
    if raw is None:
        return None
    return {
        "state": raw.get("state"),
        "score": raw.get("score"),
        "reason_code": raw.get("reason_code"),
        "critical_chain_finish_hours_delta": raw.get("critical_chain_finish_hours_delta"),
        "critical_chain_wait_hours_delta": raw.get("critical_chain_wait_hours_delta"),
        "top_impact_ops_avg_start_hours_delta": raw.get("top_impact_ops_avg_start_hours_delta"),
        "critical_chain_slack_hours_delta": raw.get("critical_chain_slack_hours_delta"),
        "critical_chain_node_count": raw.get("critical_chain_node_count"),
        "top_impact_op_count": raw.get("top_impact_op_count"),
    }


def candidate_roles_by_key(candidate_comparison: CandidateComparisonOutcome) -> Dict[str, List[str]]:
    selection = candidate_comparison.selection
    roles: Dict[str, List[str]] = {}

    def add(key: Optional[str], role: str) -> None:
        if key is None:
            return
        roles.setdefault(key, [])
        if role not in roles[key]:
            roles[key].append(role)

    if candidate_comparison.generation_policy_version == UNIFIED_GENERATION_VERSION:
        add(selection.selected_candidate_key, ROLE_RECOMMENDED)
        for objective, key in selection.objective_winners.items():
            add(key, objective)
        return roles
    add(selection.selected_candidate_key, ROLE_ADOPTED)
    add(selection.baseline_best_key, ROLE_BASELINE_BEST)
    add(selection.critical_best_key, ROLE_CRITICAL_BEST)
    return roles


def candidate_detail_saved(candidate: CandidatePlan, roles: List[str]) -> bool:
    if candidate.status != "completed":
        return False
    if candidate.generation_policy_version == UNIFIED_GENERATION_VERSION:
        return ROLE_RECOMMENDED not in roles
    if ROLE_ADOPTED in roles:
        return False
    return ROLE_BASELINE_BEST in roles or ROLE_CRITICAL_BEST in roles


def _public_failure_reason(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    reason = value.strip()
    if not reason:
        return None
    if reason in _PUBLIC_FAILURE_REASON_CODES:
        return reason
    return "candidate_failed"


def _candidate_weight(value: Optional[int], *, unified: bool) -> Optional[int]:
    """新版保留真实图参数的未知值；旧记录保持原数值口径。"""
    if unified:
        return value
    return value if value is not None else 0


def _candidate_elapsed_ms(candidate: CandidatePlan, *, unified: bool) -> Optional[int]:
    """候选耗时（秒）换算成整毫秒。"""
    if unified:
        return None
    return round(candidate.elapsed_seconds * 1000)


def candidate_graph_enabled(candidate: CandidatePlan) -> bool:
    if candidate.generation_policy_version == UNIFIED_GENERATION_VERSION:
        return candidate.origin is not None and bool(candidate.origin.get("graph_ready_profile"))
    return candidate.kind == CANDIDATE_KIND_CRITICAL_CHAIN


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


def candidate_public_summary(candidate: CandidatePlan, *, roles: Optional[List[str]] = None) -> Dict[str, Any]:
    unified = candidate.generation_policy_version == UNIFIED_GENERATION_VERSION
    score = candidate_score_summary(candidate)
    role_list = roles if roles is not None else []
    health = candidate_health_summary(candidate)
    summary: Dict[str, Any] = {
        "label": candidate.label,
        "kind": candidate.kind,
        "status": candidate.status,
        "score": score,
        "metrics": candidate_metrics_summary(candidate, score=score),
        "health": health,
        "graph_enabled": candidate_graph_enabled(candidate),
        "critical_weight": _candidate_weight(candidate.graph_critical_weight, unified=unified),
        "impact_weight": _candidate_weight(candidate.graph_impact_weight, unified=unified),
        "downstream_weight": _candidate_weight(candidate.graph_downstream_weight, unified=unified),
        "elapsed_ms": _candidate_elapsed_ms(candidate, unified=unified),
        "detail_saved": candidate_detail_saved(candidate, role_list),
        "roles": role_list,
    }
    if unified:
        summary.update(_business_candidate_fields(candidate))
    failure_reason = _public_failure_reason(candidate.failure_reason)
    if failure_reason:
        summary["failure_reason"] = failure_reason
    # Public views name the sibling by label only; candidate keys stay internal.
    reused_from_label = candidate.reused_from_label
    if reused_from_label:
        summary["reused_from_label"] = reused_from_label
    # Only a failed certification is worth a field, and only as a code: the reason text (raw exception
    # messages included) stays on the plan and in the run log, like failure_reason above.
    if candidate.input_certification.startswith(UNCERTIFIED_PREFIX):
        summary["input_certification"] = UNCERTIFIED
    summary.update(_candidate_dispatch_rule_fields(candidate))
    return summary


def candidate_comparison_public_summary(candidate_comparison: CandidateComparisonOutcome) -> Dict[str, Any]:
    selection = cast("BusinessObjectiveSelectionResult", candidate_comparison.selection)
    roles_by_key = candidate_roles_by_key(candidate_comparison)
    candidates = candidate_comparison.candidates
    return {
        "enabled": True,
        "generation_policy_version": UNIFIED_GENERATION_VERSION,
        "primary_objective": candidate_comparison.primary_objective,
        "target_objectives": list(candidate_comparison.target_objectives),
        "planned_candidate_count": len(candidates),
        "completed_candidate_count": len(candidates),
        "failed_candidate_count": 0,
        "skipped_candidate_count": 0,
        "reused_candidate_count": 0,
        "time_budget_reached": candidate_comparison.time_budget_reached,
        "run_time_budget_seconds": candidate_comparison.run_time_budget_seconds,
        "skipped_candidate_labels": [],
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
    if is_unified_generation(raw):
        return _unified_comparison_small_summary(raw)
    keys = (
        "enabled",
        "planned_candidate_count",
        "completed_candidate_count",
        "failed_candidate_count",
        "skipped_candidate_count",
        "time_budget_reached",
        "run_time_budget_seconds",
        "skipped_candidate_labels",
        "baseline_missing_or_failed",
        "selection_policy",
        "selection_reason_code",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        if key in raw:
            out[key] = raw.get(key)
    return out


def _unified_comparison_small_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "enabled", "generation_policy_version", "primary_objective", "target_objectives",
        "planned_candidate_count", "completed_candidate_count", "failed_candidate_count",
        "skipped_candidate_count", "reused_candidate_count", "time_budget_reached", "run_time_budget_seconds",
        "skipped_candidate_labels", "selection_policy_version", "selection_reason_code",
    )
    return {key: raw[key] for key in keys if key in raw}


__all__ = [
    "ROLE_ADOPTED",
    "ROLE_BASELINE_BEST",
    "ROLE_CRITICAL_BEST",
    "candidate_comparison_minimal_summary",
    "candidate_comparison_public_summary",
    "candidate_detail_saved",
    "candidate_health_summary",
    "candidate_graph_enabled",
    "candidate_metrics_summary",
    "candidate_public_summary",
    "candidate_roles_by_key",
    "candidate_score_summary",
    "is_unified_generation",
]
