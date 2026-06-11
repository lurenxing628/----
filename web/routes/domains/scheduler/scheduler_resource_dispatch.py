from __future__ import annotations

import time
from typing import Any

from flask import current_app, flash, g, jsonify, redirect, render_template, request, send_file

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, error_response
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler.resource_dispatch_excel import build_resource_dispatch_workbook
from web.error_boundary import json_error_response, user_visible_app_error_message
from web.navigation_context import set_current_workbench_navigation_context
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)
from web.viewmodels.scheduler_workbench_links import (
    RESOURCE_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_plan_context,
    can_emit_feedback_write_urls,
)

from .scheduler_bp import bp
from .scheduler_resource_dispatch_query import (
    _actual_import_url,
    _actual_record_url_template,
    _actual_template_url,
    _current_request_args,
    _data_url,
    _error_payload_with_invalid_query_keys,
    _execution_data_url,
    _export_url,
    _is_missing_history_version_error,
    _page_url,
    _request_kwargs,
    _sanitize_dispatch_args_from_error,
    execution_query_missing_context_fields,
)

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _svc() -> Any:
    return g.services.resource_dispatch_service


def _text(value: Any) -> str:
    return str(value or "").strip()


def _resource_id_from_filters(filters: Any) -> str:
    scope_type = _text(filters.get("scope_type")) if isinstance(filters, dict) else ""
    if scope_type == "machine":
        return _text(filters.get("machine_id"))
    if scope_type == "team":
        return _text(filters.get("team_id"))
    return _text(filters.get("operator_id"))


def _current_back_to() -> str:
    return _text(request.args.get("back_to"))


def _workbench_context(filters: Any, plan_identity: Any, *, back_to: Any = None) -> dict:
    filters_dict = dict(filters or {})
    identity = plan_identity if isinstance(plan_identity, dict) else {}
    resource_id = _resource_id_from_filters(filters_dict)
    resource_type = filters_dict.get("scope_type") if resource_id else None
    context = build_workbench_plan_context(
        version=filters_dict.get("version"),
        plan_role=filters_dict.get("plan_role") or identity.get("plan_role") or "adopted",
        scenario_id=filters_dict.get("scenario_id") or identity.get("scenario_id"),
        date_from=filters_dict.get("start_date"),
        date_to=filters_dict.get("end_date"),
        query_date=filters_dict.get("query_date"),
        period_preset=filters_dict.get("period_preset"),
        batch_id=filters_dict.get("batch_id"),
        resource_type=resource_type,
        resource_id=resource_id,
        can_write_feedback=identity.get("can_write_feedback") if "can_write_feedback" in identity else None,
        plan_resolution=identity,
        plan_guard_fields=RESOURCE_PLAN_GUARD_FIELDS,
        back_to=back_to,
    )
    return context


def _execution_review_link(filters: Any, plan_identity: Any, *, back_to: Any = None) -> dict:
    filters_dict = dict(filters or {})
    context = _workbench_context(filters_dict, plan_identity, back_to=back_to)
    extra_params = {}
    if filters_dict.get("team_axis"):
        extra_params["team_axis"] = filters_dict.get("team_axis")
    return build_workbench_link(context, "execution_review", extra_params=extra_params)


def _is_scenario_id_error(exc: AppError) -> bool:
    details = getattr(exc, "details", None)
    return isinstance(details, dict) and str(details.get("field") or "").strip() == "scenario_id"


def _redirect_for_sanitized_dispatch_query(exc: AppError):
    current_args = _current_request_args()
    if not current_args:
        return None
    safe_args = _sanitize_dispatch_args_from_error(exc)
    if safe_args == current_args:
        return None
    flash(user_visible_app_error_message(exc), "error")
    return redirect(_page_url(safe_args))


def _context_after_app_error(svc: Any, exc: AppError):
    if _is_missing_history_version_error(exc) or _is_scenario_id_error(exc):
        raise exc
    sanitized_redirect = _redirect_for_sanitized_dispatch_query(exc)
    if sanitized_redirect is not None:
        return sanitized_redirect
    flash(user_visible_app_error_message(exc), "error")
    return svc.build_page_context()


def _context_after_unexpected_error(svc: Any):
    current_app.logger.exception("加载资源排班页面失败")
    flash("加载资源排班页面失败，请稍后重试。", "error")
    if request.args:
        return redirect(_page_url())
    return svc.build_page_context()


def _load_resource_dispatch_context(svc: Any):
    try:
        return svc.build_page_context(**_request_kwargs())
    except AppError as exc:
        return _context_after_app_error(svc, exc)
    except Exception:
        return _context_after_unexpected_error(svc)


def _decorate_page_context(context: dict) -> dict:
    decorated_context = dict(context)
    decorated_context["versions"] = decorate_history_version_options(decorated_context.get("versions") or [])
    log_history_version_option_parse_warnings(decorated_context["versions"], log_label="资源排班页")
    return decorate_resource_dispatch_context(decorated_context)


def _execution_write_urls(filters: Any, *, can_use_current_query: bool, can_write_feedback: bool) -> dict:
    if not (can_use_current_query and can_write_feedback):
        return {
            "actual_record_url_template": None,
            "actual_template_url": None,
            "actual_import_url": None,
        }
    return {
        "actual_record_url_template": _actual_record_url_template(filters),
        "actual_template_url": _actual_template_url(filters),
        "actual_import_url": _actual_import_url(filters),
    }


def _execution_query_has_full_context() -> bool:
    return not execution_query_missing_context_fields()


@bp.get("/resource-dispatch")
def resource_dispatch_page():
    loaded_context = _load_resource_dispatch_context(_svc())
    if not isinstance(loaded_context, dict):
        return loaded_context

    context = _decorate_page_context(loaded_context)
    filters = context.get("filters") or {}
    back_to = _current_back_to()
    set_current_workbench_navigation_context(_workbench_context(filters, filters, back_to=back_to))
    can_use_current_query = bool(context.get("has_history") and context.get("can_query"))
    can_use_execution_query = can_use_current_query and _execution_query_has_full_context()
    can_write_feedback = can_emit_feedback_write_urls(filters)
    write_urls = _execution_write_urls(
        filters,
        can_use_current_query=can_use_execution_query,
        can_write_feedback=can_write_feedback,
    )

    return render_template(
        "scheduler/resource_dispatch.html",
        title="资源排班",
        data_url=_data_url(filters),
        export_url=_export_url(filters) if can_use_current_query else None,
        execution_review_link=_execution_review_link(filters, filters, back_to=back_to),
        execution_data_url=_execution_data_url(filters) if can_use_execution_query else None,
        **write_urls,
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
