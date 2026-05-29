from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from flask import request, url_for

from core.infrastructure.errors import AppError
from web.error_boundary import build_user_visible_app_error_payload, get_user_visible_field_label

_DATE_ARG_KEYS = ("period_preset", "query_date", "start_date", "end_date")
_SCOPE_ARG_KEYS = ("scope_id", "operator_id", "machine_id", "team_id")
_EXPORT_ARG_KEYS = (
    "scope_type",
    "scope_id",
    "operator_id",
    "machine_id",
    "team_id",
    "team_axis",
    "period_preset",
    "query_date",
    "start_date",
    "end_date",
    "version",
    "plan_role",
    "scenario_id",
)
_FIELD_QUERY_KEY_DROPS = {
    "scope_type": ("scope_type", *_SCOPE_ARG_KEYS),
    "scope_id": _SCOPE_ARG_KEYS,
    "operator_id": _SCOPE_ARG_KEYS,
    "machine_id": _SCOPE_ARG_KEYS,
    "team_id": _SCOPE_ARG_KEYS,
    "team_axis": ("team_axis",),
    "period_preset": _DATE_ARG_KEYS,
    "query_date": _DATE_ARG_KEYS,
    "start_date": _DATE_ARG_KEYS,
    "end_date": _DATE_ARG_KEYS,
    "date_range": _DATE_ARG_KEYS,
    "version": ("version",),
    "plan_role": ("plan_role",),
}


def _arg_text(name: str, *, default: Optional[str] = None) -> Optional[str]:
    value = request.args.get(name)
    if value is None:
        return default
    text = value.strip()
    return text or default


def _request_kwargs() -> Dict[str, Any]:
    return {
        "scope_type": _arg_text("scope_type", default="operator"),
        "scope_id": _arg_text("scope_id"),
        "operator_id": _arg_text("operator_id"),
        "machine_id": _arg_text("machine_id"),
        "team_id": _arg_text("team_id"),
        "team_axis": _arg_text("team_axis", default="operator"),
        "period_preset": _arg_text("period_preset", default="week"),
        "query_date": _arg_text("query_date"),
        "start_date": _arg_text("start_date"),
        "end_date": _arg_text("end_date"),
        "version": _arg_text("version"),
        "plan_role": _arg_text("plan_role"),
        "scenario_id": _arg_text("scenario_id"),
    }


def _current_request_args() -> Dict[str, str]:
    current: Dict[str, str] = {}
    for key in request.args.keys():
        value = request.args.get(key)
        text = str(value or "").strip()
        if text:
            current[key] = text
    return current


def _url_with_query(endpoint: str, query: Optional[Dict[str, str]] = None) -> str:
    base_url = url_for(endpoint)
    if not query:
        return base_url
    encoded = urlencode(query)
    return f"{base_url}?{encoded}" if encoded else base_url


def _page_url(query: Optional[Dict[str, str]] = None) -> str:
    return _url_with_query("scheduler.resource_dispatch_page", query)


def _query_from_filters(filters: Dict[str, Any]) -> Dict[str, str]:
    query: Dict[str, str] = {}
    for key in _EXPORT_ARG_KEYS:
        value = filters.get(key)
        text = str(value or "").strip()
        if text:
            query[key] = text
    return query


def _data_url(filters: Dict[str, Any]) -> str:
    return _url_with_query("scheduler.resource_dispatch_data", _query_from_filters(filters))


def _execution_data_url(filters: Dict[str, Any]) -> str:
    return _url_with_query("scheduler.resource_dispatch_execution_data", _query_from_filters(filters))


def _actual_template_url(filters: Dict[str, Any]) -> str:
    return _url_with_query("scheduler.resource_dispatch_actual_template", _query_from_filters(filters))


def _actual_import_url(filters: Dict[str, Any]) -> str:
    return _url_with_query("scheduler.resource_dispatch_actual_import", _query_from_filters(filters))


def _export_url(filters: Dict[str, Any]) -> str:
    query = _query_from_filters(filters)
    return _url_with_query("scheduler.resource_dispatch_export", query)


def _drop_keys(values: Dict[str, str], *keys: str) -> Dict[str, str]:
    blocked = set(keys)
    return {key: value for key, value in values.items() if key not in blocked}


def _error_field(exc: AppError) -> str:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        field = details.get("field")
        if field is not None:
            return str(field).strip()
    return ""


def _is_missing_history_version_error(exc: AppError) -> bool:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return False
    return str(details.get("field") or "").strip() == "version" and str(details.get("status") or "").strip() == "missing_history"


def _sanitize_dispatch_args_from_error(exc: AppError) -> Dict[str, str]:
    current = _current_request_args()
    if not current:
        return {}
    if _is_missing_history_version_error(exc):
        return dict(current)
    field = _error_field(exc)
    drop_keys = _FIELD_QUERY_KEY_DROPS.get(field)
    if not drop_keys:
        return dict(current)
    return _drop_keys(current, *drop_keys)


def _cleanup_query_keys_from_error(exc: AppError) -> List[str]:
    if _is_missing_history_version_error(exc):
        return []
    field = _error_field(exc)
    return list(_FIELD_QUERY_KEY_DROPS.get(field, ()))


def _error_payload_with_invalid_query_keys(exc: AppError) -> Dict[str, Any]:
    payload = build_user_visible_app_error_payload(exc)
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return payload
    details = dict(error.get("details") or {})
    cleanup_query_keys = _cleanup_query_keys_from_error(exc)
    if cleanup_query_keys:
        raw_keys = [str(key).strip() for key in cleanup_query_keys if str(key).strip()]
        labels = [get_user_visible_field_label(key) or str(key).strip() for key in cleanup_query_keys if str(key).strip()]
        details["invalid_query_keys"] = raw_keys
        details["invalid_query_labels"] = labels
        details["cleanup_query_keys"] = raw_keys
        diagnostics = dict(error.get("diagnostics") or {})
        diagnostics["invalid_query_keys"] = raw_keys
        diagnostics["invalid_query_labels"] = labels
        diagnostics["cleanup_query_keys"] = raw_keys
        error["diagnostics"] = diagnostics
    if details:
        error["details"] = details
    return payload
