from __future__ import annotations

from typing import Any, Dict, List

from .optimizer_public_safety import (
    project_attempt_score,
    project_public_metrics,
    public_float,
    public_int,
    safe_attempt_text,
    safe_bool,
    safe_metric_key,
)

PUBLIC_CANDIDATE_ROLES = {"adopted", "baseline_best", "critical_best"}
PUBLIC_CANDIDATE_STATUSES = {"completed", "failed", "skipped"}
PUBLIC_CANDIDATE_FAILURE_REASONS = {"candidate_failed", "candidate_time_budget_reached"}


def public_candidate_label(value: Any) -> str:
    raw_text = str(value or "").strip()
    if raw_text == "baseline":
        return "原算法方案"
    if raw_text.startswith("graph_w") and "_of_" in raw_text:
        parts = raw_text.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    text = safe_attempt_text(raw_text)
    if not text:
        return ""
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    has_ascii_letter = any(("a" <= ch.lower() <= "z") for ch in text)
    if "_" in text or (has_ascii_letter and not has_chinese):
        return ""
    return text


def project_best_score_schema(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        row = _project_score_schema_item(item)
        if row:
            out.append(row)
    return out


def _project_score_schema_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    key = safe_metric_key(item.get("key"))
    if not key:
        return {}
    row: Dict[str, Any] = {"key": key}
    index = public_int(item.get("index"))
    if index is not None:
        row["index"] = index
    label = public_candidate_label(item.get("label"))
    if label:
        row["label"] = label
    return row


def project_candidate_comparison(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    if "enabled" in value:
        out["enabled"] = bool(value.get("enabled"))
    out.update(_project_candidate_comparison_counts(value))
    _add_candidate_comparison_budget(out, value)
    _add_candidate_comparison_labels(out, value)
    _add_candidate_comparison_selection(out, value)
    _add_candidate_comparison_candidates(out, value)
    return out


def _project_candidate_comparison_counts(value: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in (
        "planned_candidate_count",
        "completed_candidate_count",
        "failed_candidate_count",
        "skipped_candidate_count",
    ):
        number = public_int(value.get(key))
        if number is not None:
            out[key] = number
    return out


def _add_candidate_comparison_budget(out: Dict[str, Any], value: Dict[str, Any]) -> None:
    if "time_budget_reached" in value:
        out["time_budget_reached"] = bool(value.get("time_budget_reached"))
    budget = public_float(value.get("run_time_budget_seconds"))
    if budget is not None:
        out["run_time_budget_seconds"] = budget
    if "baseline_missing_or_failed" in value:
        out["baseline_missing_or_failed"] = bool(value.get("baseline_missing_or_failed"))


def _add_candidate_comparison_labels(out: Dict[str, Any], value: Dict[str, Any]) -> None:
    labels: List[str] = []
    for item in list(value.get("skipped_candidate_labels") or []):
        label = public_candidate_label(item)
        if label:
            labels.append(label)
    if labels:
        out["skipped_candidate_labels"] = labels


def _add_candidate_comparison_selection(out: Dict[str, Any], value: Dict[str, Any]) -> None:
    reason_code = safe_attempt_text(value.get("selection_reason_code"))
    if reason_code:
        out["selection_reason_code"] = reason_code


def _add_candidate_comparison_candidates(out: Dict[str, Any], value: Dict[str, Any]) -> None:
    candidates: List[Dict[str, Any]] = []
    for candidate in list(value.get("candidates") or []):
        projected = _project_candidate_comparison_candidate(candidate)
        if projected:
            candidates.append(projected)
    if candidates:
        out["candidates"] = candidates


def _project_candidate_comparison_candidate(candidate: Any) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    out: Dict[str, Any] = {}
    _add_candidate_identity(out, candidate)
    _add_candidate_score(out, candidate)
    _add_candidate_booleans_and_weights(out, candidate)
    _add_candidate_roles_and_failure(out, candidate)
    return out


def _add_candidate_identity(out: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    label = public_candidate_label(candidate.get("label"))
    if label:
        out["label"] = label
    status = safe_attempt_text(candidate.get("status"))
    if status in PUBLIC_CANDIDATE_STATUSES:
        out["status"] = status


def _add_candidate_score(out: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    score = project_attempt_score(candidate.get("score"))
    if score:
        out["score"] = score
    metrics = project_public_metrics(candidate.get("metrics"))
    if metrics:
        out["metrics"] = metrics
    health = _project_candidate_health(candidate.get("health"))
    if health:
        out["health"] = health


def _add_candidate_booleans_and_weights(out: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    for key in ("graph_enabled", "detail_saved"):
        if key in candidate:
            out[key] = safe_bool(candidate.get(key))
    for key in ("critical_weight", "impact_weight", "downstream_weight", "elapsed_ms"):
        number = public_int(candidate.get(key))
        if number is not None:
            out[key] = number


def _add_candidate_roles_and_failure(out: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    roles = _project_candidate_roles(candidate.get("roles"))
    if roles:
        out["roles"] = roles
    failure_reason = str(candidate.get("failure_reason") or "").strip()
    if failure_reason in PUBLIC_CANDIDATE_FAILURE_REASONS:
        out["failure_reason"] = failure_reason
    elif failure_reason:
        out["failure_reason"] = "candidate_failed"


def _project_candidate_health(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    state = safe_attempt_text(value.get("state"))
    if state:
        out["state"] = state
    for key in (
        "score",
        "critical_chain_finish_hours_delta",
        "critical_chain_wait_hours_delta",
        "top_impact_ops_avg_start_hours_delta",
        "critical_chain_slack_hours_delta",
    ):
        number = public_float(value.get(key))
        if number is not None:
            out[key] = number
    for key in ("critical_chain_node_count", "top_impact_op_count"):
        number = public_int(value.get(key))
        if number is not None:
            out[key] = number
    return out


def _project_candidate_roles(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    roles: List[str] = []
    for item in value:
        role = str(item or "").strip()
        if role in PUBLIC_CANDIDATE_ROLES and role not in roles:
            roles.append(role)
    return roles


__all__ = [
    "project_best_score_schema",
    "project_candidate_comparison",
    "public_candidate_label",
]
