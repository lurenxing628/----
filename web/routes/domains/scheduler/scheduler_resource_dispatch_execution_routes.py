from __future__ import annotations

from typing import Any, Mapping

from flask import current_app, jsonify, request, send_file

from core.infrastructure.errors import AppError, ErrorCode, ValidationError, error_response
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
)
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.operation_execution_scope_read import events_for_scope
from web.viewmodels.scheduler_resource_dispatch_execution import (
    build_execution_payload,
    event_payload,
    execution_result_payload,
)

from ...excel_utils import read_uploaded_excel_bytes
from .scheduler_bp import bp
from .scheduler_resource_dispatch_execution_context import (
    _actual_record_result_payload,
    _actual_record_svc,
    _event_target_from_request,
    _execution_error_response,
    _execution_svc,
    _feedback_context,
    _feedback_context_for_task_key,
    _feedback_svc,
    _json_payload,
    _read_request_kwargs,
    _scope_for_event_list,
    _source_row_for_event_list,
    _source_row_for_task_key,
    _task_card_by_identity,
    _task_card_by_key,
    _task_card_for_result,
    _write_request_kwargs,
)

_EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@bp.get("/resource-dispatch/execution/data")
def resource_dispatch_execution_data():
    try:
        payload = build_execution_payload(_execution_svc().get_execution_context(**_read_request_kwargs()))
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
        target = _event_target_from_request(int(op_id))
        context = _execution_svc().get_execution_context(**_read_request_kwargs())
        source_row = _source_row_for_event_list(context, target)
        card_payload = build_execution_payload(context)
        task_card = _task_card_by_identity(card_payload, target)
        if task_card is None:
            raise AppError(ErrorCode.NOT_FOUND, "当前查询条件下找不到这道工序的现场记录，请刷新后重试。", details={"reason": "not_found"})
        scope = _scope_for_event_list(context, source_row)
        state = _feedback_svc().get_execution_state_for_scopes([scope]).get(scope)
        events = events_for_scope(_feedback_svc(), scope)
        machine_labels, operator_labels = _feedback_svc().resource_labels_for_events(events)
        return jsonify(
            {
                "success": True,
                "data": {
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


@bp.get("/resource-dispatch/execution/tasks/<task_key>/events")
def resource_dispatch_execution_events_by_task(task_key: str):
    try:
        context = _execution_svc().get_execution_context(**_read_request_kwargs())
        source_row = _source_row_for_task_key(context, task_key)
        card_payload = build_execution_payload(context)
        task_card = _task_card_by_key(card_payload, task_key)
        if task_card is None:
            raise AppError(ErrorCode.NOT_FOUND, "当前查询条件下找不到这道工序的现场记录，请刷新后重试。", details={"reason": "not_found"})
        scope = _scope_for_event_list(context, source_row)
        state = _feedback_svc().get_execution_state_for_scopes([scope]).get(scope)
        events = events_for_scope(_feedback_svc(), scope)
        machine_labels, operator_labels = _feedback_svc().resource_labels_for_events(events)
        return jsonify(
            {
                "success": True,
                "data": {
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


@bp.post("/resource-dispatch/execution/tasks/<task_key>/actual")
def resource_dispatch_execution_actual_by_task(task_key: str):
    action = "fill_actual"
    try:
        payload = _json_payload()
        context = _feedback_context_for_task_key(task_key, payload)
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
        data = execution_result_payload(result, _task_card_for_result(context, result))
        data["state_revision"] = result.state_revision
        return jsonify({"success": True, "data": data})
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
