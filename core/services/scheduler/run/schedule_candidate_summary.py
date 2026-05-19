from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schedule_candidate_specs import CANDIDATE_KIND_CRITICAL_CHAIN

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"


def _candidate_key(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _score_list(candidate: Any) -> Optional[List[float]]:
    score = getattr(candidate, "score", None)
    if score is None:
        return None
    return [float(item) for item in tuple(score)]


def _metric_value(metrics: Any, name: str) -> Optional[Any]:
    if metrics is None:
        return None
    if isinstance(metrics, dict):
        return metrics.get(name)
    if hasattr(metrics, "to_dict"):
        data = metrics.to_dict()
        if isinstance(data, dict):
            return data.get(name)
    return getattr(metrics, name, None)


def candidate_metrics_summary(candidate: Any) -> Dict[str, Any]:
    metrics = getattr(candidate, "metrics", None)
    score = _score_list(candidate)
    out: Dict[str, Any] = {}
    if score:
        out["failed_ops"] = int(score[0])
    for key in (
        "overdue_count",
        "total_tardiness_hours",
        "weighted_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ):
        value = _metric_value(metrics, key)
        if value is not None:
            out[key] = value
    return out


def candidate_health_summary(candidate: Any) -> Optional[Dict[str, Any]]:
    health = getattr(candidate, "health", None)
    if health is None:
        return None
    if isinstance(health, dict):
        raw = health
    elif hasattr(health, "to_dict"):
        raw = health.to_dict()
    else:
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


def candidate_roles_by_key(candidate_comparison: Any) -> Dict[str, List[str]]:
    selection = getattr(candidate_comparison, "selection", None)
    roles: Dict[str, List[str]] = {}

    def add(key: Any, role: str) -> None:
        candidate_key = _candidate_key(key)
        if candidate_key is None:
            return
        roles.setdefault(candidate_key, [])
        if role not in roles[candidate_key]:
            roles[candidate_key].append(role)

    add(getattr(selection, "selected_candidate_key", None), ROLE_ADOPTED)
    add(getattr(selection, "baseline_best_key", None), ROLE_BASELINE_BEST)
    add(getattr(selection, "critical_best_key", None), ROLE_CRITICAL_BEST)
    return roles


def candidate_detail_saved(candidate: Any, roles: List[str]) -> bool:
    status = str(getattr(candidate, "status", "") or "").strip().lower()
    if status != "completed":
        return False
    if ROLE_ADOPTED in roles:
        return False
    return ROLE_BASELINE_BEST in roles or ROLE_CRITICAL_BEST in roles


def candidate_public_summary(candidate: Any, *, roles: Optional[List[str]] = None) -> Dict[str, Any]:
    role_list = list(roles or [])
    health = candidate_health_summary(candidate)
    summary = {
        "candidate_key": str(getattr(candidate, "candidate_key", "") or ""),
        "label": str(getattr(candidate, "label", "") or ""),
        "kind": str(getattr(candidate, "kind", "") or ""),
        "status": str(getattr(candidate, "status", "") or ""),
        "score": _score_list(candidate),
        "metrics": candidate_metrics_summary(candidate),
        "health": health,
        "graph_enabled": str(getattr(candidate, "kind", "") or "") == CANDIDATE_KIND_CRITICAL_CHAIN,
        "critical_weight": int(getattr(candidate, "graph_critical_weight", 0) or 0),
        "impact_weight": int(getattr(candidate, "graph_impact_weight", 0) or 0),
        "downstream_weight": int(getattr(candidate, "graph_downstream_weight", 0) or 0),
        "elapsed_ms": int(round(float(getattr(candidate, "elapsed_seconds", 0.0) or 0.0) * 1000)),
        "detail_saved": candidate_detail_saved(candidate, role_list),
        "roles": role_list,
    }
    failure_reason = str(getattr(candidate, "failure_reason", "") or "").strip()
    if failure_reason:
        summary["failure_reason"] = failure_reason[:200]
    return summary


def candidate_comparison_public_summary(candidate_comparison: Any) -> Dict[str, Any]:
    selection = getattr(candidate_comparison, "selection", None)
    roles_by_key = candidate_roles_by_key(candidate_comparison)
    return {
        "enabled": True,
        "planned_candidate_count": int(getattr(candidate_comparison, "planned_count", 0) or 0),
        "completed_candidate_count": int(getattr(candidate_comparison, "completed_count", 0) or 0),
        "failed_candidate_count": int(getattr(candidate_comparison, "failed_count", 0) or 0),
        "skipped_candidate_count": int(getattr(candidate_comparison, "skipped_count", 0) or 0),
        "time_budget_reached": bool(getattr(candidate_comparison, "time_budget_reached", False)),
        "run_time_budget_seconds": getattr(candidate_comparison, "run_time_budget_seconds", None),
        "adopted_candidate_key": getattr(selection, "selected_candidate_key", None),
        "raw_score_best_candidate_key": getattr(selection, "raw_score_best_key", None),
        "baseline_best_candidate_key": getattr(selection, "baseline_best_key", None),
        "critical_best_candidate_key": getattr(selection, "critical_best_key", None),
        "selection_policy": getattr(selection, "selection_policy", None),
        "selection_reason_code": getattr(selection, "reason_code", None),
        "candidates": [
            candidate_public_summary(candidate, roles=roles_by_key.get(str(getattr(candidate, "candidate_key", "") or ""), []))
            for candidate in list(getattr(candidate_comparison, "candidates", None) or [])
        ],
    }


def candidate_comparison_minimal_summary(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    keys = (
        "enabled",
        "planned_candidate_count",
        "completed_candidate_count",
        "failed_candidate_count",
        "skipped_candidate_count",
        "time_budget_reached",
        "run_time_budget_seconds",
        "adopted_candidate_key",
        "raw_score_best_candidate_key",
        "baseline_best_candidate_key",
        "critical_best_candidate_key",
        "selection_policy",
        "selection_reason_code",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        if key in raw:
            out[key] = raw.get(key)
    return out


def candidate_comparison_log_summary(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    keys = (
        "enabled",
        "planned_candidate_count",
        "completed_candidate_count",
        "time_budget_reached",
        "run_time_budget_seconds",
        "adopted_candidate_key",
        "selection_policy",
        "selection_reason_code",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        if key in raw:
            out[key] = raw.get(key)
    return out


__all__ = [
    "ROLE_ADOPTED",
    "ROLE_BASELINE_BEST",
    "ROLE_CRITICAL_BEST",
    "candidate_comparison_log_summary",
    "candidate_comparison_minimal_summary",
    "candidate_comparison_public_summary",
    "candidate_detail_saved",
    "candidate_health_summary",
    "candidate_metrics_summary",
    "candidate_public_summary",
    "candidate_roles_by_key",
]
