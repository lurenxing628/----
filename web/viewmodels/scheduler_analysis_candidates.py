from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    VALID_PLAN_ROLES,
    plan_role_label,
)

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
_NO_COMPARISON_NOTICE = "本次没有开启方案对比，只生成了最终采用方案。"

_SELECTION_REASON_LABELS = {
    "score_only_raw_score_best": "本次设置为只看整体分数，系统采用综合评分最好的方案。",
    "balanced_critical_health_better": "系统综合查看交期和整体分数后，重点工序优先方案表现更合适，所以采用它。",
    "balanced_raw_score_best": "系统综合查看交期和整体分数后，采用整体评分最好、且没有明显增加拖期风险的方案。",
}

_REQUIRED_COMPARISON_ROLES = frozenset((ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST))


def _plan_role_label(role: str) -> str:
    text = str(role or "").strip()
    return plan_role_label(text) if text else "-"


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


def _adopted_candidate_key(comparison: Dict[str, Any]) -> str:
    return str(comparison.get("adopted_candidate_key") or "").strip()


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
    return _CANDIDATE_STATUS_LABELS.get(status, "状态未识别")


def _selection_reason_label(reason_code: Any) -> str:
    code = str(reason_code or "").strip()
    if not code:
        return "系统按本次设置自动选择最终采用方案。"
    return _SELECTION_REASON_LABELS.get(code, "系统按本次设置自动选择最终采用方案。")


def _candidate_label_from_key(candidate_key: str, role: str) -> str:
    key = str(candidate_key or "").strip()
    if key == "baseline":
        return "原算法方案"
    if key.startswith("graph_w") and "_of_" in key:
        parts = key.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return _plan_role_label(role)


def _candidate_label(candidate: Dict[str, Any], option: Optional[Dict[str, Any]], *, candidate_key: str, role: str) -> str:
    raw_label = str(candidate.get("label") or (option or {}).get("candidate_label") or "").strip()
    if raw_label and raw_label != str(candidate_key or "").strip():
        return raw_label.replace("关键链候选", "重点工序优先方案")
    return _candidate_label_from_key(candidate_key, role)


def _role_source_table(option: Optional[Dict[str, Any]]) -> str:
    source_table = str((option or {}).get("source_table") or "").strip()
    if source_table in (SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS):
        return source_table
    return ""


def _role_is_comparison(option: Optional[Dict[str, Any]]) -> Optional[bool]:
    source_table = _role_source_table(option)
    if not source_table:
        return None
    if "is_comparison" in (option or {}):
        return bool((option or {}).get("is_comparison"))
    return source_table == SOURCE_CANDIDATE_ROWS


def _comparison_note(*, role: str, is_comparison: bool, is_same_as_adopted: bool) -> str:
    if role == ROLE_ADOPTED:
        return ""
    if is_comparison:
        return "这是对比方案，不是正式写入的结果。"
    if is_same_as_adopted:
        return "与最终采用方案相同，正式排程已写入这一版。"
    return "这套方案从正式排程读取，正式排程已写入这一版。"


def _failed_candidate_labels(comparison: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for candidate in list(comparison.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("status") or "").strip() != "failed":
            continue
        key = str(candidate.get("candidate_key") or "").strip()
        label = str(candidate.get("label") or "").strip() or _candidate_label_from_key(key, "")
        reason = str(candidate.get("failure_reason") or "").strip()
        labels.append(f"{label}（{reason}）" if reason else label)
    return labels


def _warning_message(text: str) -> Dict[str, str]:
    return {"class_name": "flash-card flash-warning mt-2", "text": text}


def _comparison_status_messages(comparison: Dict[str, Any]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    failed_count = int(comparison.get("failed_candidate_count") or 0)
    failed_labels = _failed_candidate_labels(comparison)
    if failed_count > 0:
        suffix = f"：{'、'.join(failed_labels)}。" if failed_labels else "。"
        messages.append(_warning_message(f"本次有 {failed_count} 个候选运行失败{suffix}系统只在可用候选中自动择优。"))
    if bool(comparison.get("baseline_missing_or_failed")):
        messages.append(_warning_message("原算法候选缺失或失败，本次采用结果需复核。"))
    skipped_labels = list(comparison.get("skipped_candidate_labels") or [])
    if skipped_labels:
        messages.append(_warning_message(f"因本次时间上限跳过：{'、'.join(str(item) for item in skipped_labels)}"))
    return messages


def _has_complete_comparison_rows(rows: List[Dict[str, Any]]) -> bool:
    roles = {str(row.get("role") or "") for row in list(rows or [])}
    return _REQUIRED_COMPARISON_ROLES <= roles


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
    is_comparison = _role_is_comparison(option)
    if is_comparison is None:
        return None
    candidate_key = _candidate_key_for_role(comparison, candidates_by_key, role, key_field, option)
    if not candidate_key:
        return None

    candidate = candidates_by_key.get(candidate_key)
    if candidate is None:
        return None
    role_label = str((option or {}).get("label") or _plan_role_label(role)).replace(
        "关键链最好",
        "重点工序优先方案最好",
    )
    status = _candidate_status(candidate, option)
    adopted_key = _adopted_candidate_key(comparison)
    is_same_as_adopted = bool(candidate_key and candidate_key == adopted_key)
    comparison_note = _comparison_note(
        role=role,
        is_comparison=bool(is_comparison),
        is_same_as_adopted=is_same_as_adopted,
    )
    return {
        "role": role,
        "role_label": role_label,
        "source_table": _role_source_table(option),
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
        "is_same_as_adopted": is_same_as_adopted,
        "is_comparison": bool(is_comparison),
        "comparison_note": comparison_note,
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
        "skipped_candidate_labels": list(comparison.get("skipped_candidate_labels") or []),
        "failed_candidate_labels": _failed_candidate_labels(comparison),
        "baseline_missing_or_failed": bool(comparison.get("baseline_missing_or_failed")),
        "selection_reason_code": comparison.get("selection_reason_code"),
        "selection_reason_label": _selection_reason_label(comparison.get("selection_reason_code")),
        "status_messages": _comparison_status_messages(comparison),
        "notice": "",
        "has_comparison": True,
    }


def _incomplete_comparison_display_payload(
    *,
    comparison: Dict[str, Any],
    selected_ver: int,
    notice: str,
) -> Dict[str, Any]:
    return {
        "version": int(selected_ver),
        "rows": [],
        "available_role_count": 1,
        "planned_candidate_count": comparison.get("planned_candidate_count"),
        "completed_candidate_count": comparison.get("completed_candidate_count"),
        "failed_candidate_count": comparison.get("failed_candidate_count"),
        "skipped_candidate_count": comparison.get("skipped_candidate_count"),
        "time_budget_reached": bool(comparison.get("time_budget_reached")),
        "skipped_candidate_labels": list(comparison.get("skipped_candidate_labels") or []),
        "failed_candidate_labels": _failed_candidate_labels(comparison),
        "baseline_missing_or_failed": bool(comparison.get("baseline_missing_or_failed")),
        "selection_reason_code": comparison.get("selection_reason_code"),
        "selection_reason_label": _selection_reason_label(comparison.get("selection_reason_code")),
        "status_messages": _comparison_status_messages(comparison),
        "notice": notice,
        "has_comparison": False,
    }


def _no_comparison_display_payload(selected_ver: Optional[int]) -> Dict[str, Any]:
    return {
        "version": int(selected_ver or 0),
        "rows": [],
        "available_role_count": 1,
        "planned_candidate_count": None,
        "completed_candidate_count": None,
        "failed_candidate_count": None,
        "skipped_candidate_count": None,
        "time_budget_reached": False,
        "skipped_candidate_labels": [],
        "failed_candidate_labels": [],
        "baseline_missing_or_failed": False,
        "selection_reason_code": "",
        "selection_reason_label": "",
        "status_messages": [],
        "notice": _NO_COMPARISON_NOTICE,
        "has_comparison": False,
    }


def build_candidate_comparison_display(
    selected_summary: Optional[Dict[str, Any]],
    *,
    selected_ver: Optional[int],
    plan_role_options: Optional[List[Any]] = None,
    integrity_notice: str = "",
) -> Optional[Dict[str, Any]]:
    comparison = _candidate_comparison_summary(selected_summary)
    if selected_ver is None:
        return None
    if comparison is None:
        return _no_comparison_display_payload(selected_ver)
    if integrity_notice:
        return _incomplete_comparison_display_payload(
            comparison=comparison,
            selected_ver=int(selected_ver),
            notice=integrity_notice,
        )

    options_by_role = _plan_role_options_by_role(plan_role_options)
    candidates_by_key = _candidate_rows_by_key(comparison)
    rows = _candidate_display_rows(
        comparison=comparison,
        candidates_by_key=candidates_by_key,
        options_by_role=options_by_role,
    )

    if not _has_complete_comparison_rows(rows):
        return _incomplete_comparison_display_payload(
            comparison=comparison,
            selected_ver=int(selected_ver),
            notice="本次方案对比记录不完整，当前只展示最终采用方案。",
        )
    return _candidate_comparison_display_payload(
        comparison=comparison,
        selected_ver=int(selected_ver),
        options_by_role=options_by_role,
        rows=rows,
    )


__all__ = ["build_candidate_comparison_display"]
