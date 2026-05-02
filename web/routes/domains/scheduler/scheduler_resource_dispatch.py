from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from flask import current_app, flash, g, jsonify, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, error_response
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler.resource_dispatch_excel import build_resource_dispatch_workbook
from web.error_boundary import (
    build_user_visible_app_error_payload,
    get_user_visible_field_label,
    json_error_response,
    user_visible_app_error_message,
)
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)

from .scheduler_bp import bp

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
}


def _svc() -> Any:
    return g.services.resource_dispatch_service


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


def _export_url(filters: Dict[str, Any]) -> str:
    query: Dict[str, str] = {}
    for key in _EXPORT_ARG_KEYS:
        value = filters.get(key)
        text = str(value or "").strip()
        if text:
            query[key] = text
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


@bp.get("/resource-dispatch")
def resource_dispatch_page():
    svc = _svc()
    try:
        context = svc.build_page_context(**_request_kwargs())
    except AppError as exc:
        if _is_missing_history_version_error(exc):
            raise
        current_args = _current_request_args()
        if current_args:
            safe_args = _sanitize_dispatch_args_from_error(exc)
            if safe_args != current_args:
                flash(user_visible_app_error_message(exc), "error")
                return redirect(_page_url(safe_args))
        flash(user_visible_app_error_message(exc), "error")
        context = svc.build_page_context()
    except Exception:
        current_app.logger.exception("加载资源排班中心页面失败")
        if request.args:
            flash("加载资源排班中心页面失败，请稍后重试。", "error")
            return redirect(url_for("scheduler.resource_dispatch_page"))
        flash("加载资源排班中心页面失败，请稍后重试。", "error")
        context = svc.build_page_context()

    context = dict(context)
    context["versions"] = decorate_history_version_options(context.get("versions") or [])
    log_history_version_option_parse_warnings(context["versions"], log_label="资源排班页")
    context = decorate_resource_dispatch_context(context)
    filters = context.get("filters") or {}
    export_url = None
    if context.get("has_history") and context.get("can_query"):
        export_url = _export_url(filters)

    return render_template(
        "scheduler/resource_dispatch.html",
        title="资源排班中心",
        data_url=url_for("scheduler.resource_dispatch_data"),
        export_url=export_url,
        **context,
    )


@bp.get("/resource-dispatch/data")
def resource_dispatch_data():
    try:
        payload = decorate_resource_dispatch_payload(_svc().get_dispatch_payload(**_request_kwargs()))
        return jsonify({"success": True, "data": payload})
    except AppError as exc:
        return json_error_response(exc, payload=_error_payload_with_invalid_query_keys(exc))
    except Exception:
        current_app.logger.exception("资源排班数据生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "资源排班数据生成失败，请稍后重试。")), 500


@bp.get("/resource-dispatch/export")
def resource_dispatch_export():
    start = time.time()
    svc = _svc()
    try:
        payload = svc.get_dispatch_payload(**_request_kwargs())
        if not payload.get("has_history"):
            raise BusinessError(
                ErrorCode.NOT_FOUND,
                "暂无排产历史，无法导出资源排班。",
                details={"field": "version", "status": "no_history"},
            )
        payload = decorate_resource_dispatch_payload(payload)
        buf = build_resource_dispatch_workbook(payload)
        filename = build_resource_dispatch_filename(payload)
        filters = payload.get("filters") or {}
        summary = payload.get("summary") or {}
        detail_rows = payload.get("detail_rows") or []
        row_count = int(summary.get("total_tasks") or len(detail_rows) or 0)
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="scheduler",
            target_type="resource_dispatch",
            template_or_export_type="资源排班.xlsx",
            filters={
                "scope_type": filters.get("scope_type"),
                "scope_id": filters.get("scope_id"),
                "team_id": filters.get("team_id"),
                "team_axis": filters.get("team_axis"),
                "version": filters.get("version"),
                "period_preset": filters.get("period_preset"),
            },
            row_count=row_count,
            time_range={"start": filters.get("start_date"), "end": filters.get("end_date")},
            time_cost_ms=time_cost_ms,
            target_id=str(filters.get("version") or ""),
        )
        return send_file(buf, as_attachment=True, download_name=filename, mimetype=_EXCEL_MIMETYPE)
    except AppError as exc:
        if exc.code == ErrorCode.NOT_FOUND:
            return user_visible_app_error_message(exc), 404
        flash(user_visible_app_error_message(exc), "error")
        return redirect(_page_url(_sanitize_dispatch_args_from_error(exc)))
    except Exception:
        current_app.logger.exception("导出资源排班失败")
        flash("导出资源排班失败，请稍后重试。", "error")
    return redirect(_page_url(_current_request_args()))
