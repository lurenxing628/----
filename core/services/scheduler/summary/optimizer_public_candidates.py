from __future__ import annotations

from typing import Any, Dict

_COMPARISON_FIELDS = (
    "enabled", "generation_policy_version", "primary_objective", "target_objectives",
    "planned_candidate_count", "completed_candidate_count", "time_budget_reached", "run_time_budget_seconds",
    "selection_policy_version", "selection_reason_code", "selection", "unified_process",
)
_CANDIDATE_FIELDS = (
    "label", "kind", "status", "score", "metrics", "health", "graph_enabled", "critical_weight",
    "impact_weight", "downstream_weight", "elapsed_ms", "elapsed_seconds", "detail_saved", "roles",
    "generation_policy_version", "representative_objectives", "evaluations", "origin", "first_found_elapsed_ms",
    "search_evidence_ref", "adopted_dispatch_rule", "configured_dispatch_rule",
)


def project_candidate_comparison(value: Dict[str, Any]) -> Dict[str, Any]:
    out = {key: value[key] for key in _COMPARISON_FIELDS if key in value}
    if "candidates" in value:
        out["candidates"] = [
            {key: candidate[key] for key in _CANDIDATE_FIELDS if key in candidate}
            for candidate in value["candidates"]
        ]
    return out


__all__ = [
    "project_candidate_comparison",
]
