from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from .scheduler_workbench_links import ROLE_ADOPTED, build_workbench_plan_context

_PLAN_GUARD_FIELD_NAMES = (
    "requested_plan_role",
    "effective_plan_role",
    "plan_role_status",
    "is_scenario_preview",
    "is_comparison",
    "is_superseded_by_newer_version",
    "is_official_plan",
    "is_preview_plan",
    "is_current_executable_official_version",
    "can_dispatch",
    "can_write_feedback",
    "plan_identity_error",
    "plan_identity_blocking_error",
    "plan_identity_blocking_scope",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = _text(value)
    if len(text) >= 10:
        head = text[:10].replace("/", "-")
        parts = head.split("-")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return text


def _plan_dates(plan_time_span: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    if not isinstance(plan_time_span, dict):
        return "", ""
    return _date_text(plan_time_span.get("start_time")), _date_text(plan_time_span.get("end_time"))


def _version_value(latest_history: Any) -> Optional[int]:
    raw = getattr(latest_history, "version", None) if latest_history is not None else None
    if raw is None:
        return None
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return None
    return version if version > 0 else None


def _filter_text(filters: Dict[str, Any], key: str) -> str:
    return _text(filters.get(key))


def _first_filter_text(filters: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        text = _filter_text(filters, key)
        if text:
            return text
    return ""


def _filter_or_none(filters: Dict[str, Any], keys: Iterable[str], fallback: Any = None) -> Any:
    text = _first_filter_text(filters, keys)
    if text:
        return text
    return fallback if fallback else None


def _context_kwargs(
    filters: Dict[str, Any], *, version: Optional[int], date_from: str, date_to: str, plan_time_span_load_error: str
) -> Dict[str, Any]:
    effective_version = _filter_or_none(filters, ("version",), version)
    date_from_value = date_from if plan_time_span_load_error else _filter_or_none(filters, ("date_from",), date_from)
    date_to_value = date_to if plan_time_span_load_error else _filter_or_none(filters, ("date_to",), date_to)
    return {
        "version": effective_version,
        "plan_id": _filter_or_none(filters, ("plan_id",)),
        "plan_role": _filter_or_none(filters, ("requested_plan_role", "plan_role"), ROLE_ADOPTED),
        "plan_role_label_value": _filter_or_none(filters, ("plan_identity_label", "requested_plan_role_label"), ""),
        "scenario_id": _filter_or_none(filters, ("scenario_id",)),
        "scenario_display_label": _filter_text(filters, "scenario_display_name"),
        "date_from": date_from_value,
        "date_to": date_to_value,
        "query_date": _filter_or_none(filters, ("query_date",)),
        "period_preset": _filter_or_none(filters, ("period_preset",)),
        "batch_id": _filter_or_none(filters, ("batch_id",)),
        "resource_type": _filter_or_none(filters, ("resource_type",)),
        "resource_id": _filter_or_none(filters, ("resource_id",)),
        "resource_label": _filter_text(filters, "resource_label"),
        "back_to": _filter_or_none(filters, ("back_to",)),
        "can_write_feedback": filters.get("can_write_feedback") if "can_write_feedback" in filters else False,
    }


def latest_plan_context(
    *,
    latest_history: Any,
    plan_time_span: Optional[Dict[str, Any]],
    plan_time_span_load_error: str = "",
    navigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    date_from, date_to = _plan_dates(plan_time_span)
    filters = dict(navigation_context or {})
    context = build_workbench_plan_context(
        **_context_kwargs(
            filters,
            version=_version_value(latest_history),
            date_from=date_from,
            date_to=date_to,
            plan_time_span_load_error=_text(plan_time_span_load_error),
        )
    )
    if _text(plan_time_span_load_error):
        context["plan_time_span_load_error"] = _text(plan_time_span_load_error)
    for key in _PLAN_GUARD_FIELD_NAMES:
        if key in filters:
            context[key] = filters[key]
    return context


__all__ = ["latest_plan_context"]
