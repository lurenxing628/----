from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
)
from core.models.operation_execution_state import OperationExecutionState

_FEEDBACK_DISABLED_REASON = "现场反馈保护还没开启，暂不能提交开工或完工。"
_NOT_CURRENT_OFFICIAL_REASON = "当前不是最新正式采用方案，不能提交现场反馈。"
_ACTION_LABELS = {
    EXECUTION_EVENT_START: "开工",
    EXECUTION_EVENT_PAUSE: "暂停",
    EXECUTION_EVENT_RESUME: "继续生产",
    EXECUTION_EVENT_FINISH: "完工",
    EXECUTION_EVENT_EXCEPTION: "报异常",
    EXECUTION_ACTION_REPORT_EXCEPTION: "报异常",
}


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


def _execution_action_label(value: Any) -> str:
    return _ACTION_LABELS.get(_text(value), "操作未识别")


def _event_type_to_action(value: Any) -> str:
    text = _text(value)
    if text == EXECUTION_EVENT_EXCEPTION:
        return EXECUTION_ACTION_REPORT_EXCEPTION
    return text


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
                "label": _execution_action_label(action),
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
    available_actions = build_available_actions(
        can_write=can_write_feedback,
        feedback_write_enabled=feedback_write_enabled,
        status=status,
        status_label=status_label,
    )
    unavailable_reasons = {}
    for action in available_actions:
        action_key = str(action.get("action") or "")
        disabled_reason = _text(action.get("disabled_reason"))
        if action_key and disabled_reason:
            unavailable_reasons[action_key] = disabled_reason
    return {
        "op_id": op_id,
        "schedule_id": schedule_id,
        "batch_id": batch_id,
        "op_name": _op_name(row),
        "planned_start_time": _text(row.get("start_time")),
        "planned_end_time": _text(row.get("end_time")),
        "planned_machine_id": _text(row.get("machine_id")),
        "planned_machine_label": _resource_label(row.get("machine_id"), row.get("machine_name")),
        "planned_operator_id": _text(row.get("operator_id")),
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
        "latest_exception_reason_label": current_state.latest_exception_reason_label,
        "latest_exception_severity_label": current_state.latest_exception_severity_label,
        "latest_exception_impact_minutes_label": current_state.latest_exception_impact_minutes_label,
        "latest_exception_affected_machine_label": current_state.latest_exception_affected_machine_label,
        "latest_exception_affected_operator_label": current_state.latest_exception_affected_operator_label,
        "latest_exception_handling_status_label": current_state.latest_exception_handling_status_label,
        "latest_exception_suggest_reschedule_label": current_state.latest_exception_suggest_reschedule_label,
        "updated_at": current_state.updated_at,
        "available_actions": available_actions,
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
    action = _event_type_to_action(event_type)
    return {
        "event_id": getattr(event, "id", None),
        "op_id": getattr(event, "op_id", None),
        "schedule_id": getattr(event, "schedule_id", None),
        "action": action,
        "action_label": _execution_action_label(action),
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


__all__ = [
    "build_execution_payload",
    "build_task_card",
    "event_payload",
    "execution_result_payload",
]
