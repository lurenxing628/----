from __future__ import annotations

from typing import Any, Dict, List

from core.services.scheduler.contracts.optimizer_public_safety import (
    public_int,
    safe_metric_key,
)

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


def public_candidate_label(value: Any) -> str:
    return str(value or "").strip()


def project_best_score_schema(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        key = safe_metric_key(item.get("key"))
        if not key:
            continue
        row: Dict[str, Any] = {"key": key}
        index = public_int(item.get("index"))
        if index is not None:
            row["index"] = index
        label = public_candidate_label(item.get("label"))
        if label:
            row["label"] = label
        out.append(row)
    return out


def project_candidate_comparison(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = {key: value[key] for key in _COMPARISON_FIELDS if key in value}
    if "candidates" in value:
        out["candidates"] = [
            {key: candidate[key] for key in _CANDIDATE_FIELDS if key in candidate}
            for candidate in value["candidates"]
        ]
    return out


__all__ = [
    "project_best_score_schema",
    "project_candidate_comparison",
    "public_candidate_label",
]
