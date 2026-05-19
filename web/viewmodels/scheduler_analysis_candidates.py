from __future__ import annotations

from typing import Any, Dict, List, Optional

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
VALID_PLAN_ROLES = (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)

_PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "最终采用",
    ROLE_BASELINE_BEST: "原算法最好",
    ROLE_CRITICAL_BEST: "关键链最好",
}

_CANDIDATE_ROLE_KEY_FIELDS = (
    (ROLE_ADOPTED, "adopted_candidate_key"),
    (ROLE_BASELINE_BEST, "baseline_best_candidate_key"),
    (ROLE_CRITICAL_BEST, "critical_best_candidate_key"),
)

_CANDIDATE_STATUS_LABELS = {
    "completed": "已完成",
    "failed": "失败",
    "skipped": "已跳过",
}


def _plan_role_label(role: str) -> str:
    return _PLAN_ROLE_LABELS.get(str(role or "").strip(), str(role or "").strip() or "-")


def _dict_from_role_option(raw: Any) -> Optional[Dict[str, Any]]:
    if hasattr(raw, "to_dict"):
        data = raw.to_dict()
        return dict(data) if isinstance(data, dict) else None
    if isinstance(raw, dict):
        return dict(raw)
    return None


def _plan_role_options_by_role(plan_role_options: Optional[List[Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for raw in list(plan_role_options or []):
        option = _dict_from_role_option(raw)
        if not option:
            continue
        role = str(option.get("role") or "").strip()
        if role:
            out[role] = option
    return out


def _candidate_comparison_summary(selected_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    if not isinstance(algo, dict):
        return None
    comparison = algo.get("candidate_comparison")
    if not isinstance(comparison, dict):
        return None
    if comparison.get("enabled") is False:
        return None
    return comparison


def _candidate_rows_by_key(comparison: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for raw in list(comparison.get("candidates") or []):
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("candidate_key") or "").strip()
        if key:
            out[key] = raw
    return out


def _candidate_key_for_role(
    comparison: Dict[str, Any],
    candidates_by_key: Dict[str, Dict[str, Any]],
    role: str,
    field: str,
    option: Optional[Dict[str, Any]],
) -> str:
    key = str(comparison.get(field) or "").strip()
    if key:
        return key
    option_key = str((option or {}).get("candidate_key") or "").strip()
    if option_key:
        return option_key
    for candidate_key, candidate in candidates_by_key.items():
        roles = candidate.get("roles")
        if isinstance(roles, list) and role in roles:
            return candidate_key
    return ""


def _candidate_metric(candidate: Dict[str, Any], key: str) -> Optional[Any]:
    metrics = candidate.get("metrics") if isinstance(candidate, dict) else None
    if isinstance(metrics, dict) and key in metrics:
        return metrics.get(key)
    return None


def _candidate_failed_ops(candidate: Dict[str, Any]) -> Optional[Any]:
    metric_value = _candidate_metric(candidate, "failed_ops")
    if metric_value is not None:
        return metric_value
    score = candidate.get("score") if isinstance(candidate, dict) else None
    if isinstance(score, (list, tuple)) and score:
        return score[0]
    return None


def _candidate_score_label(candidate: Dict[str, Any]) -> str:
    score = candidate.get("score") if isinstance(candidate, dict) else None
    if isinstance(score, (list, tuple)) and score:
        return " / ".join(str(item) for item in score)
    return "-"


def _candidate_status_label(status_value: Any) -> str:
    status = str(status_value or "").strip()
    if not status:
        return "-"
    return _CANDIDATE_STATUS_LABELS.get(status, status)


def _candidate_label(candidate: Dict[str, Any], option: Optional[Dict[str, Any]], *, candidate_key: str, role: str) -> str:
    return str(candidate.get("label") or (option or {}).get("candidate_label") or candidate_key or _plan_role_label(role)).strip()


def _candidate_kind(candidate: Dict[str, Any], option: Optional[Dict[str, Any]]) -> str:
    return str(candidate.get("kind") or (option or {}).get("candidate_kind") or "")


def _candidate_status(candidate: Dict[str, Any], option: Optional[Dict[str, Any]]) -> str:
    return str(candidate.get("status") or (option or {}).get("candidate_status") or "")


def _candidate_display_row(
    *,
    comparison: Dict[str, Any],
    candidates_by_key: Dict[str, Dict[str, Any]],
    options_by_role: Dict[str, Dict[str, Any]],
    role: str,
    key_field: str,
) -> Optional[Dict[str, Any]]:
    option = options_by_role.get(role)
    candidate_key = _candidate_key_for_role(comparison, candidates_by_key, role, key_field, option)
    if not candidate_key:
        return None

    candidate = candidates_by_key.get(candidate_key, {})
    role_label = str((option or {}).get("label") or _plan_role_label(role))
    status = _candidate_status(candidate, option)
    return {
        "role": role,
        "role_label": role_label,
        "candidate_key": candidate_key,
        "candidate_label": _candidate_label(candidate, option, candidate_key=candidate_key, role=role),
        "kind": _candidate_kind(candidate, option),
        "status": status,
        "status_label": _candidate_status_label(status),
        "failed_ops": _candidate_failed_ops(candidate),
        "overdue_count": _candidate_metric(candidate, "overdue_count"),
        "total_tardiness_hours": _candidate_metric(candidate, "total_tardiness_hours"),
        "makespan_hours": _candidate_metric(candidate, "makespan_hours"),
        "changeover_count": _candidate_metric(candidate, "changeover_count"),
        "score_label": _candidate_score_label(candidate),
        "plan_role_available": role in options_by_role,
        "is_adopted": role == ROLE_ADOPTED,
        "is_comparison": role != ROLE_ADOPTED,
        "comparison_note": "" if role == ROLE_ADOPTED else "这是对比方案，不是正式写入的结果。",
        "links": {},
    }


def _candidate_display_rows(
    *,
    comparison: Dict[str, Any],
    candidates_by_key: Dict[str, Dict[str, Any]],
    options_by_role: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for role, key_field in _CANDIDATE_ROLE_KEY_FIELDS:
        row = _candidate_display_row(
            comparison=comparison,
            candidates_by_key=candidates_by_key,
            options_by_role=options_by_role,
            role=role,
            key_field=key_field,
        )
        if row is not None:
            rows.append(row)
    return rows


def _candidate_comparison_display_payload(
    *,
    comparison: Dict[str, Any],
    selected_ver: int,
    options_by_role: Dict[str, Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "version": int(selected_ver),
        "rows": rows,
        "available_role_count": sum(1 for role in VALID_PLAN_ROLES if role in options_by_role),
        "planned_candidate_count": comparison.get("planned_candidate_count"),
        "completed_candidate_count": comparison.get("completed_candidate_count"),
        "failed_candidate_count": comparison.get("failed_candidate_count"),
        "skipped_candidate_count": comparison.get("skipped_candidate_count"),
        "time_budget_reached": bool(comparison.get("time_budget_reached")),
        "selection_reason_code": comparison.get("selection_reason_code"),
    }


def build_candidate_comparison_display(
    selected_summary: Optional[Dict[str, Any]],
    *,
    selected_ver: Optional[int],
    plan_role_options: Optional[List[Any]] = None,
) -> Optional[Dict[str, Any]]:
    comparison = _candidate_comparison_summary(selected_summary)
    if comparison is None or selected_ver is None:
        return None

    options_by_role = _plan_role_options_by_role(plan_role_options)
    candidates_by_key = _candidate_rows_by_key(comparison)
    rows = _candidate_display_rows(
        comparison=comparison,
        candidates_by_key=candidates_by_key,
        options_by_role=options_by_role,
    )

    if not rows:
        return None
    return _candidate_comparison_display_payload(
        comparison=comparison,
        selected_ver=int(selected_ver),
        options_by_role=options_by_role,
        rows=rows,
    )


__all__ = ["build_candidate_comparison_display"]
