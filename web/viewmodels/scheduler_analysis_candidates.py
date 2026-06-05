from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    VALID_PLAN_ROLES,
)

from .scheduler_analysis_candidate_helpers import (
    _CANDIDATE_ROLE_KEY_FIELDS,
    _NO_COMPARISON_NOTICE,
    _REQUIRED_COMPARISON_ROLES,
    _SUMMARY_CARD_METRICS,
    _adopted_candidate_key,
    _adopted_candidate_status_message,
    _adopted_row,
    _candidate_comparison_summary,
    _candidate_key_for_role,
    _candidate_kind,
    _candidate_label,
    _candidate_metric,
    _candidate_metric_parse_failed,
    _candidate_recommendation_card,
    _candidate_rows_by_key,
    _candidate_status,
    _candidate_status_completed,
    _candidate_status_label,
    _candidate_status_public_value,
    _candidate_technical_score_label,
    _comparison_note,
    _comparison_status_messages,
    _failed_candidate_labels,
    _failure_reason_label,
    _format_metric_comparison,
    _format_metric_value,
    _has_complete_comparison_rows,
    _link_unavailable_reason,
    _plan_role_label,
    _plan_role_options_by_role,
    _public_candidate_label_text,
    _role_detail_saved,
    _role_is_comparison,
    _role_source_table,
    _selection_reason_label,
    _selection_reason_state,
    _warning_message,
)


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
    completed = _candidate_status_completed(status)
    status_label = _candidate_status_label(status)
    comparison_note = _comparison_note(
        role=role,
        is_comparison=bool(is_comparison),
        is_same_as_adopted=is_same_as_adopted,
    )
    metric_keys = (
        "failed_ops",
        "overdue_count",
        "total_tardiness_hours",
        "weighted_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    )
    metric_values = {key: _candidate_metric(candidate, key) for key in metric_keys}
    metric_failures = {f"{key}_parse_failed": _candidate_metric_parse_failed(candidate, key) for key in metric_keys}
    return {
        "role": role,
        "role_label": role_label,
        "source_table": _role_source_table(option),
        "candidate_key": candidate_key,
        "candidate_label": _candidate_label(candidate, option, candidate_key=candidate_key, role=role),
        "kind": _candidate_kind(candidate, option),
        "status": _candidate_status_public_value(status),
        "status_label": status_label,
        **metric_values,
        **metric_failures,
        "technical_score_label": _candidate_technical_score_label(candidate),
        "plan_role_available": plan_role_available,
        "detail_saved": detail_saved,
        "can_open_detail": bool(plan_role_available and detail_saved and completed),
        "link_unavailable_reason": _link_unavailable_reason(
            detail_saved=detail_saved,
            plan_role_available=plan_role_available,
            completed=completed,
            status_label=status_label,
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
        parse_failed = bool(row.get(f"{key}_parse_failed"))
        adopted_parse_failed = bool((adopted or {}).get(f"{key}_parse_failed"))
        lines.append(
            {
                "label": label,
                "value": "记录异常" if parse_failed else _format_metric_value(value, unit),
                "comparison_text": _format_metric_comparison(
                    value,
                    adopted_value,
                    unit,
                    is_adopted=is_adopted,
                    parse_failed=bool(parse_failed or adopted_parse_failed),
                ),
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
    selection_reason = _selection_reason_state(comparison.get("selection_reason_code"))
    selection_reason_label = str(selection_reason.get("label") or "")
    adopted_status_message = _adopted_candidate_status_message(rows)
    recommendation_card = None
    if not bool(selection_reason.get("parse_failed")):
        recommendation_card = _candidate_recommendation_card(
            rows,
            selection_reason_label=selection_reason_label,
        )
    if adopted_status_message:
        selection_reason_label = ""
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
        "selection_reason_code": "",
        "selection_reason_label": selection_reason_label,
        "selection_reason_parse_failed": bool(selection_reason.get("parse_failed")),
        "recommendation_card": recommendation_card,
        "summary_cards": _candidate_summary_cards(rows),
        "status_messages": _comparison_status_messages(comparison)
        + ([adopted_status_message] if adopted_status_message else []),
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
        "selection_reason_code": "",
        "selection_reason_label": _selection_reason_label(comparison.get("selection_reason_code")),
        "selection_reason_parse_failed": bool(
            _selection_reason_state(comparison.get("selection_reason_code")).get("parse_failed")
        ),
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
        "selection_reason_parse_failed": False,
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
