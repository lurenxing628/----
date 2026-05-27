from __future__ import annotations

import time
from typing import Any

from flask import current_app, flash, g, jsonify, redirect, request, send_file

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, app_error_http_status, error_response
from core.models.operation_execution_event import EXECUTION_EVENT_FINISH, EXECUTION_EVENT_START
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.operation_execution_labels import execution_action_label
from core.services.scheduler.resource_dispatch_excel import build_resource_dispatch_workbook
from core.shared.field_labels import display_field_label
from web.error_boundary import json_error_response, user_visible_app_error_message
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)
from web.viewmodels.scheduler_resource_dispatch_execution import (
    build_execution_payload,
    build_task_card,
    execution_result_payload,
)

from .scheduler_bp import bp
from .scheduler_resource_dispatch_query import (
    _current_request_args,
    _data_url,
    _error_payload_with_invalid_query_keys,
    _execution_data_url,
    _export_url,
    _is_missing_history_version_error,
    _page_url,
    _request_kwargs,
    _sanitize_dispatch_args_from_error,
)

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _svc() -> Any:
    return g.services.resource_dispatch_service


def _execution_svc() -> Any:
    return g.services.resource_dispatch_execution_service


def _feedback_svc() -> Any:
    return g.services.operation_execution_feedback_service


def _execution_error_response(exc: AppError, *, action: str = None):
    details = dict(exc.details or {})
    if "field" in details:
        details.setdefault("field_label", display_field_label(details.get("field")))
    if action and "action" not in details:
        details["action"] = action
    if "action" in details:
        details.setdefault("action_label", execution_action_label(details.get("action")))
    payload = error_response(exc.code, exc.message, details=details or None)
    return payload, app_error_http_status(exc.code)


def _feedback_not_enabled_payload(action: str) -> dict:
    return error_response(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场反馈保护还没开启，暂不能提交开工或完工。",
        details={
            "reason": "feedback_not_enabled",
            "action": action,
            "action_label": execution_action_label(action),
        },
    )


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
        execution_data_url=_execution_data_url(filters),
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


@bp.get("/resource-dispatch/execution/data")
def resource_dispatch_execution_data():
    try:
        payload = build_execution_payload(_execution_svc().get_execution_context(**_request_kwargs()))
        return jsonify({"success": True, "data": payload})
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("资源排班现场反馈任务卡生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "现场反馈任务卡生成失败，请稍后重试。")), 500


def _execution_feedback_write_allowed() -> bool:
    if not bool(current_app.config.get("TESTING")):
        return False
    return request.headers.get("X-APS-Test-Execution-Feedback", "").strip().lower() == "allow"


def _json_payload() -> dict:
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return dict(data)
    return {}


def _feedback_context(op_id: int, payload: dict) -> ExecutionFeedbackContext:
    return ExecutionFeedbackContext(
        schedule_version=payload.get("version") or payload.get("schedule_version"),
        schedule_id=payload.get("schedule_id"),
        op_id=op_id,
        expected_state_revision=payload.get("expected_state_revision"),
        created_by=payload.get("created_by"),
        idempotency_key=payload.get("idempotency_key"),
        requested_plan_role=payload.get("requested_plan_role") or payload.get("plan_role") or ROLE_ADOPTED,
        source_table=payload.get("source_table") or SOURCE_SCHEDULE,
        effective_plan_role=payload.get("effective_plan_role") or ROLE_ADOPTED,
        scenario_id=payload.get("scenario_id"),
    )


def _feedback_recheck_context(context: ExecutionFeedbackContext):
    return _execution_svc().get_execution_context(
        version=context.schedule_version,
        plan_role=context.requested_plan_role,
        scenario_id=context.scenario_id,
    )


def _ensure_current_official_feedback_context(context: ExecutionFeedbackContext, *, action: str) -> None:
    if (
        context.requested_plan_role != ROLE_ADOPTED
        or context.effective_plan_role != ROLE_ADOPTED
        or context.source_table != SOURCE_SCHEDULE
        or context.scenario_id is not None
    ):
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "当前不是最新正式采用方案，不能提交现场反馈。",
            details={"reason": "not_current_official_plan", "action": action},
        )
    view_context = _feedback_recheck_context(context)
    identity = view_context.get("plan_identity") if isinstance(view_context, dict) else {}
    if not bool((identity or {}).get("can_write_feedback")):
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "当前不是最新正式采用方案，不能提交现场反馈。",
            details={"reason": "not_current_official_plan", "action": action},
        )


def _reject_if_feedback_disabled(action: str):
    if _execution_feedback_write_allowed():
        return None
    return jsonify(_feedback_not_enabled_payload(action)), 409


def _task_card_for_result(context: ExecutionFeedbackContext, result: Any) -> dict:
    card_context = _execution_svc().task_card_for_feedback_context(context, result.state, feedback_write_enabled=True)
    cards = build_execution_payload(card_context).get("tasks") or []
    if cards:
        return cards[0]
    return build_task_card(
        {"op_id": context.op_id, "schedule_id": context.schedule_id, "batch_id": result.state.batch_id},
        result.state,
        can_write_feedback=True,
        feedback_write_enabled=True,
    )


def _record_execution_feedback(op_id: int, action: str):
    payload = _json_payload()
    try:
        context = _feedback_context(op_id, payload)
        _ensure_current_official_feedback_context(context, action=action)
        rejected = _reject_if_feedback_disabled(action)
        if rejected is not None:
            return rejected
        if action == EXECUTION_EVENT_START:
            result = _feedback_svc().start_operation(
                context,
                event_time=payload.get("event_time"),
                operator_id=payload.get("operator_id"),
                machine_id=payload.get("machine_id"),
                remark=payload.get("remark"),
            )
        else:
            result = _feedback_svc().finish_operation(
                context,
                event_time=payload.get("event_time"),
                quantity_done=payload.get("quantity_done"),
                quantity_scrapped=payload.get("quantity_scrapped"),
                remark=payload.get("remark"),
            )
        task_card = _task_card_for_result(context, result)
        return jsonify({"success": True, "data": execution_result_payload(result, task_card)})
    except AppError as exc:
        payload, status = _execution_error_response(exc, action=action)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("现场反馈提交失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "现场反馈提交失败，请稍后重试。")), 500


@bp.post("/resource-dispatch/execution/<int:op_id>/start")
def resource_dispatch_execution_start(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_START)


@bp.post("/resource-dispatch/execution/<int:op_id>/finish")
def resource_dispatch_execution_finish(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_FINISH)


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
