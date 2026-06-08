from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Mapping, Optional, cast

from flask import g, request

from core.infrastructure.errors import AppError, ErrorCode, ValidationError, app_error_http_status, error_response
from core.models.operation_execution_scope import parse_positive_execution_int
from core.models.resource_dispatch_execution_tokens import execution_state_key, execution_task_key
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.operation_execution_labels import execution_action_label
from core.services.scheduler.operation_execution_scope_read import scope_from_plan_row
from core.shared.field_labels import display_field_label
from web.viewmodels.scheduler_resource_dispatch_execution import (
    build_execution_payload,
    build_task_card,
    execution_result_payload,
)

from .scheduler_resource_dispatch_query import _request_kwargs, execution_query_missing_context_fields


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = parse_positive_execution_int(value, "execution_context")
    except ValueError:
        return None
    return parsed


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


def _required_request_kwargs(*, message: str) -> Dict[str, Any]:
    missing = execution_query_missing_context_fields()
    if missing:
        raise ValidationError(message, field="plan_identity", details={"missing_fields": missing})
    return _request_kwargs()


def _write_request_kwargs() -> Dict[str, Any]:
    return _required_request_kwargs(message="现场记录写入缺少完整计划上下文，请从资源排班页面重新进入。")


def _read_request_kwargs() -> Dict[str, Any]:
    return _required_request_kwargs(message="查看现场记录缺少完整计划上下文，请从资源排班页面重新进入。")


def _row_matches_feedback_target(row: Mapping[str, Any], *, op_id: int, schedule_id: int, batch_id: str) -> bool:
    return (
        _positive_int(row.get("op_id")) == int(op_id)
        and _positive_int(row.get("schedule_id")) == int(schedule_id)
        and _text(row.get("batch_id")) == batch_id
    )


def _row_task_key(row: Mapping[str, Any]) -> str:
    return execution_task_key(row)


def _ensure_feedback_target_in_query(context: Mapping[str, Any], op_id: int, payload: Mapping[str, Any]) -> None:
    schedule_id = _positive_int(payload.get("schedule_id"))
    batch_id = _text(payload.get("batch_id"))
    if schedule_id is None or not batch_id:
        raise ValidationError(
            "现场记录写入缺少任务定位信息，请刷新资源排班页面后重试。",
            field="schedule_id" if schedule_id is None else "batch_id",
            details={"reason": "missing_required_field"},
        )
    rows = context.get("rows") if isinstance(context, Mapping) else None
    if any(
        isinstance(row, Mapping)
        and _row_matches_feedback_target(row, op_id=int(op_id), schedule_id=int(schedule_id), batch_id=batch_id)
        for row in (rows or [])
    ):
        return
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "当前查询条件下找不到这道工序的现场记录，请刷新资源排班页面后重试。",
        details={"reason": "schedule_mismatch"},
    )


def _identity_allows_query_membership_check(identity: Mapping[str, Any]) -> bool:
    # 这里只是查询结果成员检查的短路；真正写闸在 OperationExecutionFeedbackService._load_current_official_schedule。
    return bool(identity.get("can_write_feedback"))


def _request_plan_identity_payload(op_id: int, payload: Mapping[str, Any]) -> Dict[str, Any]:
    context = _execution_svc().get_execution_context(**_write_request_kwargs())
    identity = context.get("plan_identity") if isinstance(context, dict) else None
    if not isinstance(identity, dict) or not identity:
        raise ValidationError("当前计划身份不完整，请刷新资源排班页面后重试。", field="plan_identity")
    if _identity_allows_query_membership_check(identity):
        _ensure_feedback_target_in_query(context, op_id, payload)
    return _plan_identity_payload(identity)


def _plan_identity_payload(identity: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "version": identity.get("version"),
        "requested_plan_role": identity.get("requested_plan_role"),
        "effective_plan_role": identity.get("effective_plan_role"),
        "source_table": identity.get("source_table"),
        "scenario_id": identity.get("scenario_id"),
    }


def _plan_identity_payload_from_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    identity = context.get("plan_identity") if isinstance(context, Mapping) else None
    if not isinstance(identity, dict) or not identity:
        raise ValidationError("当前计划身份不完整，请刷新资源排班页面后重试。", field="plan_identity")
    return _plan_identity_payload(identity)


def _feedback_context(op_id: int, payload: Dict[str, Any]) -> ExecutionFeedbackContext:
    identity_payload = _request_plan_identity_payload(op_id, payload)
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


def _source_row_for_task_key(context: Mapping[str, Any], task_key: str) -> Mapping[str, Any]:
    key = _text(task_key)
    if not key:
        raise ValidationError("缺少任务识别码，请刷新资源排班页面后重试。", field="task_key", details={"reason": "missing_required_field"})
    for row in context.get("rows") or []:
        if isinstance(row, Mapping) and _row_task_key(row) == key:
            return row
    raise AppError(ErrorCode.NOT_FOUND, "当前查询条件下找不到这道工序的现场记录，请刷新后重试。", details={"reason": "not_found"})


def _task_card_by_key(card_payload: Mapping[str, Any], task_key: str) -> Optional[Mapping[str, Any]]:
    key = _text(task_key)
    for item in card_payload.get("tasks") or []:
        if isinstance(item, Mapping) and _text(item.get("task_key")) == key:
            return item
    return None


def _state_for_scope(scope: Any):
    return _feedback_svc().get_execution_state_for_scopes([scope])[scope]


def _feedback_context_for_task_key(task_key: str, payload: Dict[str, Any]) -> ExecutionFeedbackContext:
    context = _execution_svc().get_execution_context(**_write_request_kwargs())
    source_row = _source_row_for_task_key(context, task_key)
    identity_payload = _plan_identity_payload_from_context(context)
    scope = _scope_for_event_list(context, source_row)
    state = _state_for_scope(scope)
    revision = str(getattr(state, "state_revision", None) or f"{int(scope.op_id)}:0:0")
    expected_state_key = execution_state_key(task_key=task_key, state_revision=revision)
    feedback_context = ExecutionFeedbackContext(
        schedule_version=cast(int, identity_payload.get("version")),
        schedule_id=int(scope.schedule_id),
        op_id=int(scope.op_id),
        batch_id=str(scope.batch_id),
        expected_state_revision=revision,
        created_by=cast(str, payload.get("created_by")),
        idempotency_key=cast(str, payload.get("idempotency_key")),
        requested_plan_role=cast(str, identity_payload.get("requested_plan_role")),
        source_table=cast(str, identity_payload.get("source_table")),
        effective_plan_role=cast(str, identity_payload.get("effective_plan_role")),
        scenario_id=identity_payload.get("scenario_id"),
    )
    if _text(payload.get("state_key")) != expected_state_key:
        replay_revision = _actual_record_svc().actual_payload_replay_state_revision(feedback_context, payload)
        if not replay_revision:
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "页面上的现场记录状态已经变化，请刷新后重试。", details={"reason": "stale_state_revision"})
        feedback_context = replace(feedback_context, expected_state_revision=replay_revision)
    return feedback_context


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
        "idempotency_reused": False,
        "task_card": cards[0] if cards else {},
    }


def _event_target_from_request(op_id: int) -> Dict[str, Any]:
    schedule_id = _positive_int(request.args.get("schedule_id"))
    batch_id = _text(request.args.get("batch_id"))
    if schedule_id is None or not batch_id:
        raise ValidationError(
            "查看现场记录缺少完整任务身份，请刷新资源排班页面后重试。",
            field="schedule_id" if schedule_id is None else "batch_id",
            details={"reason": "missing_required_field"},
        )
    return {"op_id": int(op_id), "schedule_id": int(schedule_id), "batch_id": batch_id}


def _matches_event_target(row: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    return (
        _positive_int(row.get("op_id")) == int(target["op_id"])
        and _positive_int(row.get("schedule_id")) == int(target["schedule_id"])
        and _text(row.get("batch_id")) == _text(target["batch_id"])
    )


def _task_card_by_identity(card_payload: Mapping[str, Any], target: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    return _task_card_by_key(card_payload, execution_task_key(target))


def _source_row_for_event_list(context: Mapping[str, Any], target: Mapping[str, Any]) -> Mapping[str, Any]:
    for row in context.get("rows") or []:
        if isinstance(row, Mapping) and _matches_event_target(row, target):
            return row
    raise AppError(ErrorCode.NOT_FOUND, "当前查询条件下找不到这道工序的现场记录，请刷新后重试。", details={"reason": "not_found"})


def _scope_for_event_list(context: Mapping[str, Any], source_row: Mapping[str, Any]):
    plan_identity = context.get("plan_identity") if isinstance(context, Mapping) else {}
    try:
        return scope_from_plan_row(source_row, plan_identity if isinstance(plan_identity, Mapping) else {})
    except ValueError as exc:
        raise AppError(
            ErrorCode.DB_INTEGRITY_ERROR,
            "现场记录缺少完整计划身份，请刷新页面后重试。",
            details={"reason": "missing_plan_identity"},
            cause=exc,
        ) from exc
