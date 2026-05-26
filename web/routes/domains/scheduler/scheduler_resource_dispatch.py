from __future__ import annotations

import time
from typing import Any

from flask import current_app, flash, g, jsonify, redirect, request, send_file

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, error_response
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler.resource_dispatch_excel import build_resource_dispatch_workbook
from web.error_boundary import json_error_response, user_visible_app_error_message
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)

from .scheduler_bp import bp
from .scheduler_resource_dispatch_query import (
    _current_request_args,
    _data_url,
    _error_payload_with_invalid_query_keys,
    _export_url,
    _is_missing_history_version_error,
    _page_url,
    _request_kwargs,
    _sanitize_dispatch_args_from_error,
)

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _svc() -> Any:
    return g.services.resource_dispatch_service


def _is_scenario_id_error(exc: AppError) -> bool:
    details = getattr(exc, "details", None)
    return isinstance(details, dict) and str(details.get("field") or "").strip() == "scenario_id"


@bp.get("/resource-dispatch")
def resource_dispatch_page():
    svc = _svc()
    try:
        context = svc.build_page_context(**_request_kwargs())
    except AppError as exc:
        if _is_missing_history_version_error(exc) or _is_scenario_id_error(exc):
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
        current_app.logger.exception("加载资源排班页面失败")
        if request.args:
            flash("加载资源排班页面失败，请稍后重试。", "error")
            return redirect(_page_url())
        flash("加载资源排班页面失败，请稍后重试。", "error")
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
        title="资源排班",
        data_url=_data_url(filters),
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
        raw_payload = svc.get_dispatch_payload(**_request_kwargs())
        if not raw_payload.get("has_history"):
            raise BusinessError(
                ErrorCode.NOT_FOUND,
                "暂无排产历史，无法导出资源排班。",
                details={"field": "version", "status": "no_history"},
            )
        internal_filters = raw_payload.get("filters") or {}
        payload = decorate_resource_dispatch_payload(raw_payload)
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
                "requested_plan_role": internal_filters.get("requested_plan_role"),
                "effective_plan_role": internal_filters.get("effective_plan_role"),
                "plan_role_status": internal_filters.get("plan_role_status"),
                "candidate_id": internal_filters.get("candidate_id"),
                "candidate_key": internal_filters.get("candidate_key"),
                "scenario_id": internal_filters.get("scenario_id"),
                "scenario_name": internal_filters.get("scenario_name"),
                "is_scenario_preview": filters.get("is_scenario_preview"),
                "period_preset": filters.get("period_preset"),
            },
            row_count=row_count,
            time_range={"start": filters.get("start_date"), "end": filters.get("end_date")},
            time_cost_ms=time_cost_ms,
            target_id=str(filters.get("version") or ""),
        )
        return send_file(buf, as_attachment=True, download_name=filename, mimetype=_EXCEL_MIMETYPE)
    except AppError as exc:
        if _is_scenario_id_error(exc):
            return user_visible_app_error_message(exc), 400
        if exc.code == ErrorCode.NOT_FOUND:
            return user_visible_app_error_message(exc), 404
        flash(user_visible_app_error_message(exc), "error")
        return redirect(_page_url(_sanitize_dispatch_args_from_error(exc)))
    except Exception:
        current_app.logger.exception("导出资源排班失败")
        flash("导出资源排班失败，请稍后重试。", "error")
    return redirect(_page_url(_current_request_args()))
