from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.infrastructure.errors import AppError, ErrorCode, app_error_http_status, error_response
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_START,
)
from core.models.operation_execution_state import OperationExecutionState
from core.services.scheduler.operation_execution_labels import event_type_to_action, execution_action_label
from core.shared.field_labels import display_field_label

_FEEDBACK_DISABLED_REASON = "现场反馈保护还没开启，暂不能提交开工或完工。"
_NOT_CURRENT_OFFICIAL_REASON = "当前不是最新正式采用方案，不能提交现场反馈。"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resource_label(resource_id: Any, resource_name: Any) -> str:
    rid = _text(resource_id)
    name = _text(resource_name)
    return f"{rid} {name}".strip() if rid else name


def _op_name(row: Mapping[str, Any]) -> str:
    op_code = _text(row.get("op_code"))
    if op_code:
        return op_code
    batch_id = _text(row.get("batch_id"))
    seq = _text(row.get("seq"))
    return " ".join(part for part in (batch_id, f"工序{seq}" if seq else "工序") if part) or "未命名工序"


def _as_state(value: Any, op_id: int, batch_id: str) -> OperationExecutionState:
    if isinstance(value, OperationExecutionState):
        return value
    return OperationExecutionState(op_id=int(op_id), batch_id=batch_id)


def _action_enabled(*, action: str, can_write: bool, feedback_write_enabled: bool, status: str) -> bool:
    if not can_write or not feedback_write_enabled:
        return False
    if action == EXECUTION_EVENT_START:
        return status == "not_started"
    if action == EXECUTION_EVENT_FINISH:
        return status in {"processing", "paused", "exception"}
    return False


def _action_disabled_reason(*, enabled: bool, can_write: bool, feedback_write_enabled: bool, status_label: str, action: str) -> str:
    if enabled:
        return ""
    if not can_write:
        return _NOT_CURRENT_OFFICIAL_REASON
    if not feedback_write_enabled:
        return _FEEDBACK_DISABLED_REASON
    if action == EXECUTION_EVENT_START:
        return f"当前状态是{status_label}，不能开工。"
    if action == EXECUTION_EVENT_FINISH:
        return f"当前状态是{status_label}，不能完工。"
    return "当前不能执行这个操作。"


def build_available_actions(*, can_write: bool, feedback_write_enabled: bool, status: str, status_label: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for action in (EXECUTION_EVENT_START, EXECUTION_EVENT_FINISH):
        enabled = _action_enabled(
            action=action,
            can_write=can_write,
            feedback_write_enabled=feedback_write_enabled,
            status=status,
        )
        actions.append(
            {
                "action": action,
                "label": execution_action_label(action),
                "enabled": enabled,
                "disabled_reason": _action_disabled_reason(
                    enabled=enabled,
                    can_write=can_write,
                    feedback_write_enabled=feedback_write_enabled,
                    status_label=status_label,
                    action=action,
                ),
            }
        )
    return actions


def build_task_card(row: Mapping[str, Any], state: Any, *, can_write_feedback: bool, feedback_write_enabled: bool) -> Dict[str, Any]:
    op_id = _positive_int(row.get("op_id")) or 0
    schedule_id = _positive_int(row.get("schedule_id")) or 0
    batch_id = _text(row.get("batch_id"))
    current_state = _as_state(state, op_id, batch_id)
    status = _text(current_state.current_status) or "not_started"
    status_label = _text(current_state.current_status_label) or "待开工"
    unavailable_reasons: List[str] = []
    if not can_write_feedback:
        unavailable_reasons.append(_NOT_CURRENT_OFFICIAL_REASON)
    if can_write_feedback and not feedback_write_enabled:
        unavailable_reasons.append(_FEEDBACK_DISABLED_REASON)
    return {
        "op_id": op_id,
        "schedule_id": schedule_id,
        "batch_id": batch_id,
        "op_name": _op_name(row),
        "planned_start_time": _text(row.get("start_time")),
        "planned_end_time": _text(row.get("end_time")),
        "planned_machine_label": _resource_label(row.get("machine_id"), row.get("machine_name")),
        "planned_operator_label": _resource_label(row.get("operator_id"), row.get("operator_name")),
        "current_status": status,
        "current_status_label": status_label,
        "state_revision": current_state.state_revision or f"{op_id}:0:0",
        "actual_start_time": current_state.actual_start_time,
        "actual_end_time": current_state.actual_end_time,
        "actual_machine_label": current_state.actual_machine_label,
        "actual_operator_label": current_state.actual_operator_label,
        "last_event_action_label": current_state.last_event_action_label,
        "last_event_remark": current_state.last_event_remark,
        "updated_at": current_state.updated_at,
        "available_actions": build_available_actions(
            can_write=can_write_feedback,
            feedback_write_enabled=feedback_write_enabled,
            status=status,
            status_label=status_label,
        ),
        "unavailable_reasons": unavailable_reasons,
    }


def build_execution_payload(context: Mapping[str, Any]) -> Dict[str, Any]:
    can_write = bool(context.get("can_write_feedback"))
    feedback_write_enabled = bool(context.get("feedback_write_enabled"))
    states = context.get("states") if isinstance(context.get("states"), dict) else {}
    tasks: List[Dict[str, Any]] = []
    for row in context.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        op_id = _positive_int(row.get("op_id"))
        if op_id is None:
            continue
        tasks.append(
            build_task_card(
                row,
                states.get(op_id),
                can_write_feedback=can_write,
                feedback_write_enabled=feedback_write_enabled,
            )
        )
    disabled_reason = ""
    if not can_write:
        disabled_reason = _NOT_CURRENT_OFFICIAL_REASON
    elif not feedback_write_enabled:
        disabled_reason = _FEEDBACK_DISABLED_REASON
    return {
        "plan_identity": dict(context.get("plan_identity") or {}),
        "plan_identity_label": _text(context.get("plan_identity_label")) or "正式采用方案",
        "can_write_feedback": can_write,
        "disabled_reason": disabled_reason,
        "tasks": tasks,
    }


def event_payload(event: Any) -> Dict[str, Any]:
    event_type = _text(getattr(event, "event_type", ""))
    action = event_type_to_action(event_type)
    return {
        "event_id": getattr(event, "id", None),
        "op_id": getattr(event, "op_id", None),
        "schedule_id": getattr(event, "schedule_id", None),
        "action": action,
        "action_label": execution_action_label(action),
        "event_time": getattr(event, "event_time", None),
        "created_by": getattr(event, "created_by", None),
        "remark": getattr(event, "remark", None),
        "reason_code": getattr(event, "reason_code", None),
        "reason_label": None,
        "severity": getattr(event, "severity", None),
        "severity_label": None,
        "impact_minutes": getattr(event, "impact_minutes", None),
        "impact_minutes_label": None,
        "affected_machine_label": None,
        "affected_operator_label": None,
        "handling_status_label": None,
        "suggest_reschedule_label": None,
    }


def execution_result_payload(result: Any, task_card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": event_payload(result.event),
        "current_status": result.state.current_status,
        "current_status_label": result.state.current_status_label,
        "state_revision": result.state_revision,
        "idempotency_reused": bool(result.idempotency_reused),
        "task_card": task_card,
    }


def feedback_not_enabled_payload(action: str) -> Dict[str, Any]:
    return error_response(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场反馈保护还没开启，暂不能提交开工或完工。",
        details={
            "reason": "feedback_not_enabled",
            "action": action,
            "action_label": execution_action_label(action),
        },
    )


def preserve_execution_error_response(exc: AppError, *, action: Optional[str] = None):
    details = dict(exc.details or {})
    if "field" in details:
        details.setdefault("field_label", display_field_label(details.get("field")))
    if action and "action" not in details:
        details["action"] = action
    if "action" in details:
        details.setdefault("action_label", execution_action_label(details.get("action")))
    payload = error_response(exc.code, exc.message, details=details or None)
    return payload, app_error_http_status(exc.code)


__all__ = [
    "build_execution_payload",
    "build_task_card",
    "event_payload",
    "execution_result_payload",
    "feedback_not_enabled_payload",
    "preserve_execution_error_response",
]
