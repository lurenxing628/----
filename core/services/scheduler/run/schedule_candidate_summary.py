from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from core.models.schedule_plan_role import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST

from .optimizer.shared_process import _numeric_score
from .schedule_candidate_plan import CANDIDATE_KIND_CRITICAL_CHAIN, UNCERTIFIED, UNCERTIFIED_PREFIX

if TYPE_CHECKING:
    from .schedule_candidate_selection import BusinessObjectiveSelectionResult

UNIFIED_GENERATION_VERSION = "unified_search_v1"
ROLE_RECOMMENDED = "recommended"

_PUBLIC_FAILURE_REASON_CODES = {
    "candidate_failed",
    "candidate_time_budget_reached",
}


def _candidate_key(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def is_unified_generation(value: Any) -> bool:
    version = value.get("generation_policy_version") if isinstance(value, dict) else getattr(value, "generation_policy_version", None)
    return version == UNIFIED_GENERATION_VERSION


def candidate_score_summary(candidate: Any) -> Optional[List[Any]]:
    score = getattr(candidate, "score", None)
    if score is None:
        return None
    if is_unified_generation(candidate):
        primary = _candidate_text(candidate, "objective_name") or _candidate_text(candidate, "objective")
        evaluation = (getattr(candidate, "evaluations", None) or {}).get(primary) or {}
        scope = evaluation.get("scoring_scope") or {}
        return _numeric_score(score, components_known=scope.get("components_known") is True)
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
    score = candidate_score_summary(candidate)
    out: Dict[str, Any] = {}
    if score and score[0] is not None:
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
    if is_unified_generation(candidate):
        return None
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

    if is_unified_generation(candidate_comparison):
        add(getattr(selection, "selected_candidate_key", None), ROLE_RECOMMENDED)
        for objective, key in (getattr(selection, "objective_winners", None) or {}).items():
            add(key, objective)
        return roles
    add(getattr(selection, "selected_candidate_key", None), ROLE_ADOPTED)
    add(getattr(selection, "baseline_best_key", None), ROLE_BASELINE_BEST)
    add(getattr(selection, "critical_best_key", None), ROLE_CRITICAL_BEST)
    return roles


def candidate_detail_saved(candidate: Any, roles: List[str]) -> bool:
    status = str(getattr(candidate, "status", "") or "").strip().lower()
    if status != "completed":
        return False
    if is_unified_generation(candidate):
        return ROLE_RECOMMENDED not in roles
    if ROLE_ADOPTED in roles:
        return False
    return ROLE_BASELINE_BEST in roles or ROLE_CRITICAL_BEST in roles


def _public_failure_reason(value: Any) -> Optional[str]:
    reason = str(value or "").strip()
    if not reason:
        return None
    if reason in _PUBLIC_FAILURE_REASON_CODES:
        return reason
    return "candidate_failed"


def _candidate_text(candidate: Any, name: str) -> str:
    """读取候选的文本属性；缺失或空值统一按空字符串对外。"""
    return str(getattr(candidate, name, "") or "")


def _candidate_weight(candidate: Any, name: str) -> Optional[int]:
    """新版保留真实图参数的未知值；旧记录保持原数值口径。"""
    if is_unified_generation(candidate):
        value = getattr(candidate, name, None)
        return None if value is None else int(value)
    return int(getattr(candidate, name, 0) or 0)


def _candidate_elapsed_ms(candidate: Any) -> Optional[int]:
    """候选耗时（秒）换算成整毫秒。"""
    if is_unified_generation(candidate):
        return None
    return int(round(float(getattr(candidate, "elapsed_seconds", 0.0) or 0.0) * 1000))


def candidate_graph_enabled(candidate: Any) -> bool:
    if is_unified_generation(candidate):
        origin = getattr(candidate, "origin", None) or {}
        return bool(origin.get("graph_ready_profile"))
    return _candidate_text(candidate, "kind") == CANDIDATE_KIND_CRITICAL_CHAIN


def _business_candidate_fields(candidate: Any) -> Dict[str, Any]:
    return {
        "generation_policy_version": UNIFIED_GENERATION_VERSION,
        "representative_objectives": list(getattr(candidate, "representative_objectives", None) or []),
        "evaluations": dict(getattr(candidate, "evaluations", None) or {}),
        "origin": dict(getattr(candidate, "origin", None) or {}),
        "first_found_elapsed_ms": getattr(candidate, "first_found_elapsed_ms", None),
        "search_evidence_ref": getattr(candidate, "search_evidence_ref", None),
        "elapsed_seconds": {"value": None, "state": "not_applicable", "reason": "shared_run_time"},
    }


def _candidate_dispatch_rule_fields(candidate: Any) -> Dict[str, str]:
    """公开视图的派工规则字段：实际采用的规则，以及与之不同时的配置规则。"""
    # The optimizer searches the whole rule pool; say which rule the plan really uses.
    fields: Dict[str, str] = {}
    adopted_rule = _candidate_text(candidate, "adopted_dispatch_rule")
    if adopted_rule:
        fields["adopted_dispatch_rule"] = adopted_rule
        configured_rule = _candidate_text(candidate, "dispatch_rule")
        if configured_rule and configured_rule != adopted_rule:
            fields["configured_dispatch_rule"] = configured_rule
    return fields


def candidate_public_summary(candidate: Any, *, roles: Optional[List[str]] = None) -> Dict[str, Any]:
    role_list = list(roles or [])
    health = candidate_health_summary(candidate)
    summary: Dict[str, Any] = {
        "label": _candidate_text(candidate, "label"),
        "kind": _candidate_text(candidate, "kind"),
        "status": _candidate_text(candidate, "status"),
        "score": candidate_score_summary(candidate),
        "metrics": candidate_metrics_summary(candidate),
        "health": health,
        "graph_enabled": candidate_graph_enabled(candidate),
        "critical_weight": _candidate_weight(candidate, "graph_critical_weight"),
        "impact_weight": _candidate_weight(candidate, "graph_impact_weight"),
        "downstream_weight": _candidate_weight(candidate, "graph_downstream_weight"),
        "elapsed_ms": _candidate_elapsed_ms(candidate),
        "detail_saved": candidate_detail_saved(candidate, role_list),
        "roles": role_list,
    }
    if is_unified_generation(candidate):
        summary.update(_business_candidate_fields(candidate))
    failure_reason = _public_failure_reason(getattr(candidate, "failure_reason", ""))
    if failure_reason:
        summary["failure_reason"] = failure_reason
    # Public views name the sibling by label only; candidate keys stay internal.
    reused_from_label = _candidate_text(candidate, "reused_from_label")
    if reused_from_label:
        summary["reused_from_label"] = reused_from_label
    # Only a failed certification is worth a field, and only as a code: the reason text (raw exception
    # messages included) stays on the plan and in the run log, like failure_reason above.
    if _candidate_text(candidate, "input_certification").startswith(UNCERTIFIED_PREFIX):
        summary["input_certification"] = UNCERTIFIED
    summary.update(_candidate_dispatch_rule_fields(candidate))
    return summary


def candidate_comparison_public_summary(candidate_comparison: Any) -> Dict[str, Any]:
    selection = getattr(candidate_comparison, "selection", None)
    roles_by_key = candidate_roles_by_key(candidate_comparison)
    if is_unified_generation(candidate_comparison):
        unified_selection = cast("BusinessObjectiveSelectionResult", selection)
        candidates = list(getattr(candidate_comparison, "candidates", None) or [])
        return {
            "enabled": True,
            "generation_policy_version": UNIFIED_GENERATION_VERSION,
            "primary_objective": getattr(candidate_comparison, "primary_objective", None),
            "target_objectives": list(getattr(candidate_comparison, "target_objectives", None) or []),
            "planned_candidate_count": len(candidates),
            "completed_candidate_count": len(candidates),
            "failed_candidate_count": 0,
            "skipped_candidate_count": 0,
            "reused_candidate_count": 0,
            "time_budget_reached": bool(getattr(candidate_comparison, "time_budget_reached", False)),
            "run_time_budget_seconds": getattr(candidate_comparison, "run_time_budget_seconds", None),
            "skipped_candidate_labels": [],
            "selection_policy_version": getattr(selection, "selection_policy_version", None),
            "selection_reason_code": getattr(selection, "reason_code", None),
            "selection": unified_selection.to_dict(),
            "unified_process": getattr(candidate_comparison, "unified_process", None),
            "candidates": [candidate_public_summary(candidate, roles=roles_by_key.get(candidate.candidate_key, []))
                           for candidate in candidates],
        }
    return {
        "enabled": True,
        "planned_candidate_count": int(getattr(candidate_comparison, "planned_count", 0) or 0),
        "completed_candidate_count": int(getattr(candidate_comparison, "completed_count", 0) or 0),
        "failed_candidate_count": int(getattr(candidate_comparison, "failed_count", 0) or 0),
        "skipped_candidate_count": int(getattr(candidate_comparison, "skipped_count", 0) or 0),
        "reused_candidate_count": int(getattr(candidate_comparison, "reused_count", 0) or 0),
        "time_budget_reached": bool(getattr(candidate_comparison, "time_budget_reached", False)),
        "run_time_budget_seconds": getattr(candidate_comparison, "run_time_budget_seconds", None),
        "skipped_candidate_labels": list(getattr(candidate_comparison, "skipped_candidate_labels", []) or []),
        "baseline_missing_or_failed": bool(getattr(candidate_comparison, "baseline_missing_or_failed", False)),
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
