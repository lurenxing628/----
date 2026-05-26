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
_NO_COMPARISON_NOTICE = "本次没有开启方案对比，只生成了正式采用方案。"

_SELECTION_REASON_LABELS = {
    "score_only_raw_score_best": "本次设置为只看整体表现，系统选择了整体表现更合适的方案。",
    "balanced_critical_health_better": "系统综合查看交期和整体表现后，选择了重点工序优先方案。",
    "balanced_raw_score_best": "系统综合查看交期和整体表现后，选择了整体表现更好、且没有明显增加拖期风险的方案。",
}

_FAILURE_REASON_LABELS = {
    "candidate_time_budget_reached": "试算时间到了，系统没有继续算这套方案",
}

_REQUIRED_COMPARISON_ROLES = frozenset((ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST))

_SUMMARY_CARD_METRICS = (
    ("failed_ops", "失败工序", "道"),
    ("overdue_count", "超期批次", "批"),
    ("total_tardiness_hours", "总拖期", "小时"),
    ("weighted_tardiness_hours", "加权拖期", "小时"),
    ("makespan_hours", "总工期", "小时"),
    ("changeover_count", "换型次数", "次"),
)


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


def _candidate_technical_score_label(candidate: Dict[str, Any]) -> str:
    score = candidate.get("score") if isinstance(candidate, dict) else None
    if isinstance(score, (list, tuple)) and score:
        return " / ".join(str(item) for item in score)
    return "-"


def _metric_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number


def _format_metric_value(value: Any, unit: str) -> str:
    number = _metric_number(value)
    if number is None:
        return "暂无数据"
    if abs(number - round(number)) < 0.0001:
        text = str(int(round(number)))
    else:
        text = f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{text} {unit}" if unit else text


def _format_metric_comparison(value: Any, adopted_value: Any, unit: str, *, is_adopted: bool) -> str:
    if is_adopted:
        return "作为对比基准"
    current = _metric_number(value)
    adopted = _metric_number(adopted_value)
    if current is None or adopted is None:
        return "暂无对比数据"
    delta = current - adopted
    if abs(delta) < 0.0001:
        return "和正式采用方案基本持平"
    direction = "多了" if delta > 0 else "少了"
    return f"比正式采用方案{direction} {_format_metric_value(abs(delta), unit)}"


def _candidate_status_label(status_value: Any) -> str:
    status = str(status_value or "").strip()
    if not status:
        return "-"
    return _CANDIDATE_STATUS_LABELS.get(status, "状态未识别")


def _selection_reason_label(reason_code: Any) -> str:
    code = str(reason_code or "").strip()
    if not code:
        return "系统按本次设置自动选择正式采用方案。"
    return _SELECTION_REASON_LABELS.get(code, "系统按本次设置自动选择正式采用方案。")


def _failure_reason_label(reason_value: Any) -> str:
    reason = str(reason_value or "").strip()
    if not reason:
        return ""
    mapped = _FAILURE_REASON_LABELS.get(reason)
    if mapped:
        return mapped
    if any(marker in reason for marker in ("\n", "\r", "_", "Traceback", "Exception", "Error")):
        return "没有完整原因说明"
    if any(("a" <= ch.lower() <= "z") for ch in reason):
        return "没有完整原因说明"
    return reason


def _candidate_label_from_key(candidate_key: str, role: str) -> str:
    key = str(candidate_key or "").strip()
    if key == "baseline":
        return "原算法方案"
    if key.startswith("graph_w") and "_of_" in key:
        parts = key.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return _plan_role_label(role)


def _public_candidate_label_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = (
        text.replace("关键链候选", "重点工序优先方案")
        .replace("原算法候选", "原算法方案")
        .replace("重点工序优先方案最好", "重点工序优先代表方案")
        .replace("重点工序优先最好", "重点工序优先代表方案")
        .replace("关键链最好", "重点工序优先代表方案")
        .replace("原算法最好", "原算法代表方案")
        .replace("最终采用方案", "正式采用方案")
        .replace("最终采用", "正式采用方案")
        .replace("综合评分", "整体表现")
        .replace("整体评分", "整体表现")
    )
    if text == "baseline":
        return "原算法方案"
    if text.startswith("graph_w") and "_of_" in text:
        parts = text.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return text


def _candidate_label(candidate: Dict[str, Any], option: Optional[Dict[str, Any]], *, candidate_key: str, role: str) -> str:
    raw_label = _public_candidate_label_text(candidate.get("label") or (option or {}).get("candidate_label"))
    if raw_label and raw_label != str(candidate_key or "").strip():
        return raw_label
    return _candidate_label_from_key(candidate_key, role)


def _role_source_table(option: Optional[Dict[str, Any]]) -> str:
    source_table = str((option or {}).get("source_table") or "").strip()
    if source_table in (SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS):
        return source_table
    return ""


def _role_is_comparison(option: Optional[Dict[str, Any]], *, role: str) -> Optional[bool]:
    source_table = _role_source_table(option)
    if not source_table:
        return None
    if role != ROLE_ADOPTED:
        return True
    if "is_comparison" in (option or {}):
        return bool((option or {}).get("is_comparison"))
    return source_table == SOURCE_CANDIDATE_ROWS


def _role_detail_saved(option: Optional[Dict[str, Any]]) -> bool:
    source_table = _role_source_table(option)
    if source_table == SOURCE_SCHEDULE:
        return True
    return str((option or {}).get("detail_saved") or "").strip().lower() == "yes"


def _link_unavailable_reason(*, detail_saved: bool, plan_role_available: bool) -> str:
    if not plan_role_available:
        return "这套方案记录不完整，当前无法查看明细。"
    if not detail_saved:
        return "这套对比参考方案没有保存明细，当前无法查看明细。"
    return ""


def _comparison_note(*, role: str, is_comparison: bool, is_same_as_adopted: bool) -> str:
    if role == ROLE_ADOPTED:
        return ""
    if is_comparison:
        if is_same_as_adopted:
            return "与正式采用方案相同，只作对比参考查看，不能直接派工或反馈。"
        return "这是对比参考方案，不是正式采用方案，不能直接派工或反馈。"
    if is_same_as_adopted:
        return "与正式采用方案相同，只作对比参考查看，不能直接派工或反馈。"
    return "这是对比参考方案，不是正式采用方案，不能直接派工或反馈。"


def _failed_candidate_labels(comparison: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for candidate in list(comparison.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("status") or "").strip() != "failed":
            continue
        key = str(candidate.get("candidate_key") or "").strip()
        raw_label = _public_candidate_label_text(candidate.get("label"))
        label = raw_label if raw_label != key else ""
        label = label or _candidate_label_from_key(key, "")
        reason = _failure_reason_label(candidate.get("failure_reason"))
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
        messages.append(_warning_message(f"这次有 {failed_count} 个试算方案没算成功{suffix}系统只在算成功的方案里选结果。"))
    if bool(comparison.get("baseline_missing_or_failed")):
        messages.append(_warning_message("原算法那套方案缺失或没算成功，请复核这次采用的结果。"))
    skipped_labels = [
        label
        for label in (
            _public_candidate_label_text(item) for item in list(comparison.get("skipped_candidate_labels") or [])
        )
        if label
    ]
    if skipped_labels:
        messages.append(_warning_message(f"因为时间到了，系统没再开始这些方案：{'、'.join(str(item) for item in skipped_labels)}"))
    return messages


def _has_complete_comparison_rows(rows: List[Dict[str, Any]]) -> bool:
    roles = {str(row.get("role") or "") for row in list(rows or [])}
    return _REQUIRED_COMPARISON_ROLES <= roles


def _adopted_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for row in list(rows or []):
        if str(row.get("role") or "") == ROLE_ADOPTED:
            return row
    return None


def _candidate_recommendation_card(
    rows: List[Dict[str, Any]],
    *,
    selection_reason_label: str,
) -> Optional[Dict[str, str]]:
    adopted = _adopted_row(rows)
    if not adopted:
        return None
    candidate_label = str(adopted.get("candidate_label") or adopted.get("role_label") or "").strip()
    if not candidate_label:
        return None
    reason = str(selection_reason_label or "").strip() or "系统按本次设置自动选择正式采用方案。"
    return {
        "eyebrow": "推荐结论",
        "title": "系统建议采用",
        "candidate_label": candidate_label,
        "reason": reason,
        "note": "这套方案是正式采用方案；表格里的其它代表方案只用来对照查看，不能直接派工或提交现场反馈。",
    }


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
    is_comparison = _role_is_comparison(option, role=role)
    if is_comparison is None:
        return None
    candidate_key = _candidate_key_for_role(comparison, candidates_by_key, role, key_field, option)
    if not candidate_key:
        return None

    candidate = candidates_by_key.get(candidate_key)
    if candidate is None:
        return None
    role_label = _public_candidate_label_text((option or {}).get("label") or _plan_role_label(role))
    status = _candidate_status(candidate, option)
    adopted_key = _adopted_candidate_key(comparison)
    is_same_as_adopted = bool(candidate_key and candidate_key == adopted_key)
    plan_role_available = role in options_by_role
    detail_saved = _role_detail_saved(option)
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
        "weighted_tardiness_hours": _candidate_metric(candidate, "weighted_tardiness_hours"),
        "makespan_hours": _candidate_metric(candidate, "makespan_hours"),
        "changeover_count": _candidate_metric(candidate, "changeover_count"),
        "technical_score_label": _candidate_technical_score_label(candidate),
        "plan_role_available": plan_role_available,
        "detail_saved": detail_saved,
        "can_open_detail": bool(plan_role_available and detail_saved),
        "link_unavailable_reason": _link_unavailable_reason(
            detail_saved=detail_saved,
            plan_role_available=plan_role_available,
        ),
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


def _summary_metric_lines(row: Dict[str, Any], adopted: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    is_adopted = str(row.get("role") or "") == ROLE_ADOPTED
    for key, label, unit in _SUMMARY_CARD_METRICS:
        value = row.get(key)
        adopted_value = (adopted or {}).get(key)
        lines.append(
            {
                "label": label,
                "value": _format_metric_value(value, unit),
                "comparison_text": _format_metric_comparison(value, adopted_value, unit, is_adopted=is_adopted),
            }
        )
    return lines


def _candidate_summary_cards(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not _has_complete_comparison_rows(rows):
        return []
    adopted = _adopted_row(rows)
    if not adopted:
        return []
    cards: List[Dict[str, Any]] = []
    for row in list(rows or []):
        cards.append(
            {
                "role_label": row.get("role_label") or "",
                "candidate_label": row.get("candidate_label") or "",
                "is_adopted": str(row.get("role") or "") == ROLE_ADOPTED,
                "tone_class": "aps-summary-item-success"
                if str(row.get("role") or "") == ROLE_ADOPTED
                else "aps-summary-item-neutral",
                "comparison_note": row.get("comparison_note") or "正式采用方案，作为对比基准。",
                "metrics": _summary_metric_lines(row, adopted),
            }
        )
    return cards


def _candidate_comparison_display_payload(
    *,
    comparison: Dict[str, Any],
    selected_ver: int,
    options_by_role: Dict[str, Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    selection_reason_label = _selection_reason_label(comparison.get("selection_reason_code"))
    return {
        "version": int(selected_ver),
        "rows": rows,
        "available_role_count": sum(1 for role in VALID_PLAN_ROLES if role in options_by_role),
        "planned_candidate_count": comparison.get("planned_candidate_count"),
        "completed_candidate_count": comparison.get("completed_candidate_count"),
        "failed_candidate_count": comparison.get("failed_candidate_count"),
        "skipped_candidate_count": comparison.get("skipped_candidate_count"),
        "time_budget_reached": bool(comparison.get("time_budget_reached")),
        "skipped_candidate_labels": [
            label
            for label in (
                _public_candidate_label_text(item)
                for item in list(comparison.get("skipped_candidate_labels") or [])
            )
            if label
        ],
        "failed_candidate_labels": _failed_candidate_labels(comparison),
        "baseline_missing_or_failed": bool(comparison.get("baseline_missing_or_failed")),
        "selection_reason_code": comparison.get("selection_reason_code"),
        "selection_reason_label": selection_reason_label,
        "recommendation_card": _candidate_recommendation_card(
            rows,
            selection_reason_label=selection_reason_label,
        ),
        "summary_cards": _candidate_summary_cards(rows),
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
        "skipped_candidate_labels": [
            label
            for label in (
                _public_candidate_label_text(item)
                for item in list(comparison.get("skipped_candidate_labels") or [])
            )
            if label
        ],
        "failed_candidate_labels": _failed_candidate_labels(comparison),
        "baseline_missing_or_failed": bool(comparison.get("baseline_missing_or_failed")),
        "selection_reason_code": comparison.get("selection_reason_code"),
        "selection_reason_label": _selection_reason_label(comparison.get("selection_reason_code")),
        "recommendation_card": None,
        "summary_cards": [],
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
        "recommendation_card": None,
        "summary_cards": [],
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
            notice="本次方案对比记录不完整，当前只展示正式采用方案。",
        )
    return _candidate_comparison_display_payload(
        comparison=comparison,
        selected_ver=int(selected_ver),
        options_by_role=options_by_role,
        rows=rows,
    )


__all__ = ["build_candidate_comparison_display"]
