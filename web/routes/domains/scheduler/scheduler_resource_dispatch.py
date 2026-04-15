from __future__ import annotations

import time
from typing import Any, Dict, Optional

from flask import current_app, flash, g, jsonify, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler import ResourceDispatchService
from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import bp

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DATE_ARG_KEYS = ("period_preset", "query_date", "start_date", "end_date")
_SCOPE_ARG_KEYS = ("scope_id", "operator_id", "machine_id", "team_id")
_DATE_ERROR_FIELDS = {"period_preset", "查询日期", "开始日期", "结束日期", "日期范围"}


def _svc() -> ResourceDispatchService:
    return ResourceDispatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))


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
    for key, value in request.args.to_dict(flat=True).items():
        text = str(value or "").strip()
        if text:
            current[key] = text
    return current


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


def _sanitize_dispatch_args_from_error(exc: AppError) -> Dict[str, str]:
    current = _current_request_args()
    if not current:
        return {}
    field = _error_field(exc)
    if field in _DATE_ERROR_FIELDS:
        return _drop_keys(current, *_DATE_ARG_KEYS)
    if field == "scope_type":
        return _drop_keys(current, "scope_type", *_SCOPE_ARG_KEYS)
    if field == "scope_id":
        return _drop_keys(current, *_SCOPE_ARG_KEYS)
    if field == "team_axis":
        return _drop_keys(current, "team_axis")
    if field == "version":
        return _drop_keys(current, "version")
    return {}


@bp.get("/resource-dispatch")
def resource_dispatch_page():
    svc = _svc()
    try:
        context = svc.build_page_context(**_request_kwargs())
    except AppError as exc:
        current_args = _current_request_args()
        if current_args:
            safe_args = _sanitize_dispatch_args_from_error(exc)
            if safe_args != current_args:
                flash(exc.message, "error")
                return redirect(url_for("scheduler.resource_dispatch_page", **safe_args))
        flash(exc.message, "error")
        context = svc.build_page_context()
    except Exception:
        current_app.logger.exception("加载资源排班中心页面失败")
        if request.args:
            flash("加载资源排班中心页面失败，请稍后重试。", "error")
            return redirect(url_for("scheduler.resource_dispatch_page"))
        flash("加载资源排班中心页面失败，请稍后重试。", "error")
        context = svc.build_page_context()

    filters = context.get("filters") or {}
    export_url = None
    if context.get("has_history") and context.get("can_query"):
        export_url = url_for(
            "scheduler.resource_dispatch_export",
            scope_type=filters.get("scope_type"),
            scope_id=filters.get("scope_id"),
            operator_id=filters.get("operator_id"),
            machine_id=filters.get("machine_id"),
            team_id=filters.get("team_id"),
            team_axis=filters.get("team_axis"),
            period_preset=filters.get("period_preset"),
            query_date=filters.get("query_date"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            version=filters.get("version"),
        )

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
        payload = _svc().get_dispatch_payload(**_request_kwargs())
        return jsonify({"success": True, "data": payload})
    except AppError as exc:
        return jsonify({"success": False, "error": {"code": exc.code.value, "message": exc.message}}), 400
    except Exception:
        current_app.logger.exception("资源排班数据生成失败")
        return jsonify(
            {"success": False, "error": {"code": "UNKNOWN", "message": "资源排班数据生成失败，请稍后重试。"}}
        ), 500


@bp.get("/resource-dispatch/export")
def resource_dispatch_export():
    start = time.time()
    svc = _svc()
    try:
        buf, filename, payload = svc.build_export(**_request_kwargs())
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
        flash(exc.message, "error")
    except Exception:
        current_app.logger.exception("导出资源排班失败")
        flash("导出资源排班失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_dict(flat=True)))
