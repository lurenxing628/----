from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, cast

from flask import current_app, g, jsonify, request, send_file

from core.infrastructure.errors import AppError, ErrorCode, ValidationError, app_error_http_status, error_response
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
)
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.operation_execution_labels import execution_action_label
from core.shared.field_labels import display_field_label
from web.viewmodels.scheduler_resource_dispatch_execution import (
    build_execution_payload,
    build_task_card,
    event_payload,
    execution_result_payload,
)

from ...excel_utils import read_uploaded_excel_bytes
from .scheduler_bp import bp
from .scheduler_resource_dispatch_query import _request_kwargs

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_WRITE_QUERY_REQUIRED_FIELDS = ("version", "plan_role", "period_preset", "query_date", "start_date", "end_date", "scope_type")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _execution_svc() -> Any:
    return g.services.resource_dispatch_execution_service


def _feedback_svc() -> Any:
    return g.services.operation_execution_feedback_service


def _actual_record_svc() -> Any:
    return g.services.resource_dispatch_actual_record_service


def _execution_error_response(exc: AppError, *, action: Optional[str] = None):
    details = dict(exc.details or {})
    if "field" in details:
        details.setdefault("field_label", display_field_label(details.get("field")))
    if action and "action" not in details:
        details["action"] = action
    if "action" in details:
        details.setdefault("action_label", execution_action_label(details.get("action")))
    details.setdefault("can_retry", _execution_error_can_retry(details.get("reason")))
    payload = error_response(exc.code, exc.message, details=details or None)
    return payload, app_error_http_status(exc.code)


def _execution_error_can_retry(reason: Any) -> bool:
    return str(reason or "").strip() in {
        "stale_state_revision",
        "idempotency_conflict",
        "schedule_mismatch",
        "missing_required_field",
        "invalid_field_value",
        "actual_import_validation_failed",
    }


def _json_payload() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return dict(data)
    raise ValidationError("提交内容不是有效 JSON，请刷新后重试。", field="payload")


def _write_request_kwargs() -> Dict[str, Any]:
    raw_query = {
        "version": request.args.get("version"),
        "plan_role": request.args.get("plan_role"),
        "period_preset": request.args.get("period_preset"),
        "query_date": request.args.get("query_date"),
        "start_date": request.args.get("start_date") or request.args.get("date_from"),
        "end_date": request.args.get("end_date") or request.args.get("date_to"),
        "scope_type": request.args.get("scope_type"),
    }
    missing = [key for key in _WRITE_QUERY_REQUIRED_FIELDS if not _text(raw_query.get(key))]
    if missing:
        raise ValidationError(
            "现场记录写入缺少完整计划上下文，请从资源排班页面重新进入。",
            field="plan_identity",
            details={"missing_fields": missing},
        )
    return _request_kwargs()


def _request_plan_identity_payload() -> Dict[str, Any]:
    query_kwargs = _write_request_kwargs()
    context = _execution_svc().get_execution_context(**query_kwargs)
    identity = context.get("plan_identity") if isinstance(context, dict) else None
    if not isinstance(identity, dict) or not identity:
        raise ValidationError("当前计划身份不完整，请刷新资源排班页面后重试。", field="plan_identity")
    return {
        "version": identity.get("version"),
        "requested_plan_role": identity.get("requested_plan_role"),
        "effective_plan_role": identity.get("effective_plan_role"),
        "source_table": identity.get("source_table"),
        "scenario_id": identity.get("scenario_id"),
    }


def _feedback_context(op_id: int, payload: Dict[str, Any]) -> ExecutionFeedbackContext:
    identity_payload = _request_plan_identity_payload()
    return ExecutionFeedbackContext(
        schedule_version=cast(int, identity_payload.get("version")),
        schedule_id=cast(int, payload.get("schedule_id")),
        op_id=op_id,
        batch_id=cast(str, payload.get("batch_id")),
        expected_state_revision=cast(str, payload.get("expected_state_revision")),
        created_by=cast(str, payload.get("created_by")),
        idempotency_key=cast(str, payload.get("idempotency_key")),
        requested_plan_role=cast(str, identity_payload.get("requested_plan_role")),
        source_table=cast(str, identity_payload.get("source_table")),
        effective_plan_role=cast(str, identity_payload.get("effective_plan_role")),
        scenario_id=identity_payload.get("scenario_id"),
    )


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


def _actual_record_result_payload(context: ExecutionFeedbackContext, result: Any) -> dict:
    state = result.get("state") if isinstance(result, dict) else None
    service_result = result.get("result") if isinstance(result, dict) else None
    if service_result is not None:
        return execution_result_payload(service_result, _task_card_for_result(context, service_result))
    card_context = _execution_svc().task_card_for_feedback_context(context, state, feedback_write_enabled=True)
    cards = build_execution_payload(card_context).get("tasks") or []
    return {
        "event": None,
        "current_status": getattr(state, "current_status", None),
        "current_status_label": getattr(state, "current_status_label", None),
        "state_revision": getattr(state, "state_revision", None),
        "idempotency_reused": False,
        "task_card": cards[0] if cards else {},
    }


@bp.get("/resource-dispatch/execution/data")
def resource_dispatch_execution_data():
    try:
        payload = build_execution_payload(_execution_svc().get_execution_context(**_request_kwargs()))
        return jsonify({"success": True, "data": payload})
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("资源派工现场记录任务卡生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "现场记录任务卡生成失败，请稍后重试。")), 500


@bp.get("/resource-dispatch/execution/<int:op_id>/events")
def resource_dispatch_execution_events(op_id: int):
    try:
        card_payload = build_execution_payload(_execution_svc().get_execution_context(**_request_kwargs()))
        task_card = next((item for item in card_payload.get("tasks") or [] if int(item.get("op_id") or 0) == int(op_id)), None)
        if task_card is None:
            raise AppError(ErrorCode.NOT_FOUND, "当前查询条件下找不到这道工序的现场记录，请刷新后重试。", details={"reason": "not_found"})
        states = _feedback_svc().get_execution_state([int(op_id)])
        state = states.get(int(op_id))
        events = _feedback_svc().list_execution_events(int(op_id))
        machine_labels, operator_labels = _feedback_svc().resource_labels_for_events(events)
        return jsonify(
            {
                "success": True,
                "data": {
                    "op_id": int(op_id),
                    "task_card": task_card,
                    "events": [
                        event_payload(event, state, machine_labels=machine_labels, operator_labels=operator_labels)
                        for event in events
                    ],
                },
            }
        )
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("现场记录加载失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "现场记录加载失败，请稍后重试。")), 500


@bp.post("/resource-dispatch/execution/<int:op_id>/actual")
def resource_dispatch_execution_actual(op_id: int):
    action = "fill_actual"
    try:
        payload = _json_payload()
        context = _feedback_context(op_id, payload)
        result = _actual_record_svc().record_actual_situation(context, payload)
        return jsonify({"success": True, "data": _actual_record_result_payload(context, result)})
    except AppError as exc:
        payload, status = _execution_error_response(exc, action=action)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("填写实际情况失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "填写实际情况失败，请稍后重试。")), 500


def _record_execution_feedback(op_id: int, action: str):
    try:
        payload = _json_payload()
        context = _feedback_context(op_id, payload)
        result = _record_legacy_action(context, action, payload)
        return jsonify({"success": True, "data": execution_result_payload(result, _task_card_for_result(context, result))})
    except AppError as exc:
        payload, status = _execution_error_response(exc, action=action)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("现场记录提交失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "现场记录提交失败，请稍后重试。")), 500


def _record_legacy_action(context: ExecutionFeedbackContext, action: str, payload: Mapping[str, Any]) -> Any:
    if action == EXECUTION_EVENT_START:
        return _feedback_svc().start_operation(
            context,
            event_time=payload.get("event_time"),
            operator_id=payload.get("operator_id"),
            machine_id=payload.get("machine_id"),
            remark=payload.get("remark"),
        )
    if action == EXECUTION_EVENT_FINISH:
        return _feedback_svc().finish_operation(
            context,
            event_time=payload.get("event_time"),
            quantity_done=payload.get("quantity_done"),
            quantity_scrapped=payload.get("quantity_scrapped"),
            remark=payload.get("remark"),
        )
    if action == EXECUTION_EVENT_PAUSE:
        return _feedback_svc().pause_operation(
            context,
            event_time=payload.get("event_time"),
            reason_code=payload.get("reason_code"),
            remark=payload.get("remark"),
        )
    if action == EXECUTION_EVENT_RESUME:
        return _feedback_svc().resume_operation(context, event_time=payload.get("event_time"), remark=payload.get("remark"))
    return _feedback_svc().report_exception(
        context,
        event_time=payload.get("event_time"),
        reason_code=payload.get("reason_code"),
        severity=payload.get("severity"),
        impact_minutes=payload.get("impact_minutes"),
        affected_machine_id=payload.get("affected_machine_id"),
        affected_operator_id=payload.get("affected_operator_id"),
        handling_status=payload.get("handling_status") or "new",
        suggest_reschedule=payload.get("suggest_reschedule"),
        remark=payload.get("remark"),
        reason_detail=payload.get("reason_detail"),
    )


@bp.post("/resource-dispatch/execution/<int:op_id>/start")
def resource_dispatch_execution_start(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_START)


@bp.post("/resource-dispatch/execution/<int:op_id>/finish")
def resource_dispatch_execution_finish(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_FINISH)


@bp.post("/resource-dispatch/execution/<int:op_id>/pause")
def resource_dispatch_execution_pause(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_PAUSE)


@bp.post("/resource-dispatch/execution/<int:op_id>/resume")
def resource_dispatch_execution_resume(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_EVENT_RESUME)


@bp.post("/resource-dispatch/execution/<int:op_id>/report-exception")
def resource_dispatch_execution_report_exception(op_id: int):
    return _record_execution_feedback(op_id, EXECUTION_ACTION_REPORT_EXCEPTION)


@bp.get("/resource-dispatch/execution/actual-template")
def resource_dispatch_actual_template():
    try:
        buf = _actual_record_svc().build_template_workbook(**_write_request_kwargs())
        return send_file(
            buf,
            as_attachment=True,
            download_name="现场实际情况填写模板.xlsx",
            mimetype=_EXCEL_MIMETYPE,
        )
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("下载现场实际情况模板失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "下载填写模板失败，请稍后重试。")), 500


def _uploaded_excel_bytes() -> bytes:
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件。", field="file")
    return read_uploaded_excel_bytes(file)


@bp.post("/resource-dispatch/execution/import/preview")
def resource_dispatch_actual_import_preview():
    try:
        payload = _actual_record_svc().preview_import_workbook(_uploaded_excel_bytes(), **_write_request_kwargs())
        return jsonify({"success": True, "data": payload})
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("导入实际情况预览失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "导入实际情况预览失败，请稍后重试。")), 500


@bp.post("/resource-dispatch/execution/import")
def resource_dispatch_actual_import():
    try:
        result = _actual_record_svc().import_workbook(_uploaded_excel_bytes(), **_write_request_kwargs())
        return jsonify({"success": True, "data": result})
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("导入实际情况失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "导入实际情况失败，请稍后重试。")), 500


@bp.post("/resource-dispatch/execution/import/confirm")
def resource_dispatch_actual_import_confirm():
    try:
        payload = _json_payload()
        result = _actual_record_svc().confirm_import(
            payload.get("raw_rows") or payload.get("rows") or [],
            payload.get("preview_token"),
            **_write_request_kwargs(),
        )
        return jsonify({"success": True, "data": result})
    except AppError as exc:
        payload, status = _execution_error_response(exc)
        return jsonify(payload), status
    except Exception:
        current_app.logger.exception("确认导入实际情况失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "确认导入实际情况失败，请稍后重试。")), 500
