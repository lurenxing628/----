from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
)
from core.models.operation_execution_labels import (
    EXECUTION_ACTION_FILL_ACTUAL,
    EXECUTION_ACTION_VIEW_RECORDS,
    exception_reason_label,
    execution_action_label,
    handling_status_label,
    internal_remark_tokens_from_event,
    public_execution_remark,
    severity_label,
    suggest_reschedule_label,
)
from core.models.operation_execution_state import OperationExecutionState
from core.models.resource_identity import ResourceIdentity, build_resource_identity

_FEEDBACK_DISABLED_REASON = "现场记录保护还没开启，暂不能填写现场记录。"
_NOT_CURRENT_OFFICIAL_REASON = "当前不是最新正式采用方案，不能填写现场记录。"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resource_identity(resource_id: Any = None, resource_name: Any = None) -> ResourceIdentity:
    return build_resource_identity(resource_id=resource_id, resource_name=resource_name)


def _resource_payload(prefix: str, identity: ResourceIdentity) -> Dict[str, Optional[str]]:
    payload = identity.to_dict(prefix)
    return {key: (value or None) for key, value in payload.items()}


def _resource_from_mapping(resources: Mapping[str, Any], resource_id: Any) -> ResourceIdentity:
    rid = _text(resource_id)
    if not rid:
        return build_resource_identity()
    value = resources.get(rid)
    if isinstance(value, ResourceIdentity):
        return value
    if isinstance(value, Mapping):
        return build_resource_identity(
            resource_id=value.get("id") or rid,
            resource_name=value.get("name"),
            display_label=value.get("display_label"),
            identity_label=value.get("identity_label") or value.get("label"),
        )
    if value:
        label = _text(value)
        return build_resource_identity(resource_id=rid, display_label=label, identity_label=label)
    return build_resource_identity(resource_id=rid)


def _resource_from_state(state: Any, prefix: str) -> ResourceIdentity:
    current_state = state if isinstance(state, OperationExecutionState) else None
    if current_state is None:
        return build_resource_identity()
    return build_resource_identity(
        resource_id=getattr(current_state, f"{prefix}_id", None),
        resource_name=getattr(current_state, f"{prefix}_name", None),
        display_label=getattr(current_state, f"{prefix}_display_label", None),
        identity_label=getattr(current_state, f"{prefix}_identity_label", None)
        or getattr(current_state, f"{prefix}_label", None),
    )


def _prefer_state_identity(identity: ResourceIdentity, state_identity: ResourceIdentity) -> ResourceIdentity:
    if identity.name or identity.display_label != identity.id or not state_identity.label:
        return identity
    return state_identity


def _latest_exception_resource_identities(
    *,
    event: Any,
    state: Any,
    machine_labels: Mapping[str, Any],
    operator_labels: Mapping[str, Any],
    is_exception_event: bool,
) -> Dict[str, ResourceIdentity]:
    affected_machine_id = _text(getattr(event, "affected_machine_id", None))
    affected_operator_id = _text(getattr(event, "affected_operator_id", None))
    affected_machine = _resource_from_mapping(machine_labels, affected_machine_id)
    affected_operator = _resource_from_mapping(operator_labels, affected_operator_id)
    current_state = state if isinstance(state, OperationExecutionState) else None
    if (
        is_exception_event
        and current_state is not None
        and getattr(event, "id", None) == current_state.latest_exception_event_id
    ):
        affected_machine = _prefer_state_identity(
            affected_machine,
            _resource_from_state(current_state, "latest_exception_affected_machine"),
        )
        affected_operator = _prefer_state_identity(
            affected_operator,
            _resource_from_state(current_state, "latest_exception_affected_operator"),
        )
    return {
        "affected_machine": affected_machine if is_exception_event else build_resource_identity(),
        "affected_operator": affected_operator if is_exception_event else build_resource_identity(),
    }


def _exception_payload_fields(event: Any, *, is_exception_event: bool) -> Dict[str, Optional[str]]:
    if not is_exception_event:
        return {
            "impact_minutes_label": None,
            "handling_status_label": None,
            "suggest_reschedule_label": None,
        }
    return {
        "impact_minutes_label": _impact_minutes_label(getattr(event, "impact_minutes", None)),
        "handling_status_label": handling_status_label(getattr(event, "handling_status", None)),
        "suggest_reschedule_label": suggest_reschedule_label(getattr(event, "suggest_reschedule", None)),
    }


def _execution_action_label(value: Any) -> str:
    return execution_action_label(value)


def _event_type_to_action(value: Any) -> str:
    text = _text(value)
    if text == EXECUTION_EVENT_EXCEPTION:
        return EXECUTION_ACTION_REPORT_EXCEPTION
    return text


def _impact_minutes_label(value: Any) -> Optional[str]:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return "暂时不知道影响多久"
    return f"预计影响 {minutes} 分钟" if minutes >= 0 else "暂时不知道影响多久"


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


def _fill_actual_disabled_reason(*, can_write: bool, feedback_write_enabled: bool, status_label: str) -> str:
    if not can_write:
        return _NOT_CURRENT_OFFICIAL_REASON
    if not feedback_write_enabled:
        return _FEEDBACK_DISABLED_REASON
    return f"当前状态是{status_label}，不能填写实际情况。"


def build_available_actions(*, can_write: bool, feedback_write_enabled: bool, status: str, status_label: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    fill_enabled = bool(can_write and feedback_write_enabled and status != "completed")
    if can_write:
        fill_disabled_reason = "" if fill_enabled else _fill_actual_disabled_reason(
            can_write=can_write,
            feedback_write_enabled=feedback_write_enabled,
            status_label=status_label,
        )
        actions.append({
            "action": EXECUTION_ACTION_FILL_ACTUAL,
            "label": _execution_action_label(EXECUTION_ACTION_FILL_ACTUAL),
            "enabled": fill_enabled,
            "disabled_reason": fill_disabled_reason,
        })
    actions.append({
        "action": EXECUTION_ACTION_VIEW_RECORDS,
        "label": _execution_action_label(EXECUTION_ACTION_VIEW_RECORDS),
        "enabled": True,
        "disabled_reason": "",
    })
    return actions


def build_task_card(row: Mapping[str, Any], state: Any, *, can_write_feedback: bool, feedback_write_enabled: bool) -> Dict[str, Any]:
    op_id = _positive_int(row.get("op_id")) or 0
    schedule_id = _positive_int(row.get("schedule_id")) or 0
    batch_id = _text(row.get("batch_id"))
    current_state = _as_state(state, op_id, batch_id)
    status = _text(current_state.current_status) or "not_started"
    status_label = _text(current_state.current_status_label) or "待开工"
    planned_machine = _resource_identity(row.get("machine_id"), row.get("machine_name"))
    planned_operator = _resource_identity(row.get("operator_id"), row.get("operator_name"))
    actual_machine = _resource_from_state(current_state, "actual_machine")
    actual_operator = _resource_from_state(current_state, "actual_operator")
    affected_machine = _resource_from_state(current_state, "latest_exception_affected_machine")
    affected_operator = _resource_from_state(current_state, "latest_exception_affected_operator")
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
        **_resource_payload("planned_machine_", planned_machine),
        **_resource_payload("planned_operator_", planned_operator),
        "current_status": status,
        "current_status_label": status_label,
        "state_revision": current_state.state_revision or f"{op_id}:0:0",
        "actual_start_time": current_state.actual_start_time,
        "actual_end_time": current_state.actual_end_time,
        **_resource_payload("actual_machine_", actual_machine),
        **_resource_payload("actual_operator_", actual_operator),
        "last_event_action_label": current_state.last_event_action_label,
        "last_event_remark": current_state.last_event_remark,
        "latest_exception_reason_label": current_state.latest_exception_reason_label,
        "latest_exception_severity_label": current_state.latest_exception_severity_label,
        "latest_exception_impact_minutes_label": current_state.latest_exception_impact_minutes_label,
        **_resource_payload("latest_exception_affected_machine_", affected_machine),
        **_resource_payload("latest_exception_affected_operator_", affected_operator),
        "latest_exception_handling_status_label": current_state.latest_exception_handling_status_label,
        "latest_exception_suggest_reschedule_label": current_state.latest_exception_suggest_reschedule_label,
        "latest_exception_remark": current_state.latest_exception_remark,
        "updated_at": current_state.updated_at,
        "available_actions": available_actions,
        "unavailable_reasons": unavailable_reasons,
    }


def build_execution_payload(context: Mapping[str, Any]) -> Dict[str, Any]:
    can_write = bool(context.get("can_write_feedback"))
    feedback_write_enabled = bool(context.get("feedback_write_enabled"))
    plan_identity_value = context.get("plan_identity")
    plan_identity: Mapping[str, Any] = plan_identity_value if isinstance(plan_identity_value, Mapping) else {}
    plan_identity_label = (
        _text(context.get("plan_identity_label"))
        or _text(plan_identity.get("user_label") or plan_identity.get("label"))
        or "正式采用方案"
    )
    states_value = context.get("states")
    states = states_value if isinstance(states_value, dict) else {}
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
        "plan_identity": {
            "label": plan_identity_label,
            "can_write_feedback": can_write,
            "guardrail_text": "" if can_write else disabled_reason,
        },
        "plan_identity_label": plan_identity_label,
        "can_write_feedback": can_write,
        "disabled_reason": disabled_reason,
        "tasks": tasks,
    }


def event_payload(
    event: Any,
    state: Any = None,
    *,
    machine_labels: Optional[Mapping[str, Any]] = None,
    operator_labels: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    event_type = _text(getattr(event, "event_type", ""))
    action = _event_type_to_action(event_type)
    is_exception_event = action == EXECUTION_ACTION_REPORT_EXCEPTION
    internal_tokens = internal_remark_tokens_from_event(event)
    remark = (
        public_execution_remark(getattr(event, "remark", None), internal_tokens=internal_tokens)
        or public_execution_remark(getattr(event, "reason_detail", None), internal_tokens=internal_tokens)
        or None
    )
    machines = machine_labels or {}
    operators = operator_labels or {}
    actual_machine_id = _text(getattr(event, "actual_machine_id", None))
    actual_operator_id = _text(getattr(event, "actual_operator_id", None))
    actual_machine = _resource_from_mapping(machines, actual_machine_id)
    actual_operator = _resource_from_mapping(operators, actual_operator_id)
    state_actual_machine = _resource_from_state(state, "actual_machine")
    state_actual_operator = _resource_from_state(state, "actual_operator")
    if actual_machine_id and state_actual_machine.id == actual_machine_id:
        actual_machine = _prefer_state_identity(actual_machine, state_actual_machine)
    if actual_operator_id and state_actual_operator.id == actual_operator_id:
        actual_operator = _prefer_state_identity(actual_operator, state_actual_operator)
    resource_identities = _latest_exception_resource_identities(
        event=event,
        state=state,
        machine_labels=machines,
        operator_labels=operators,
        is_exception_event=is_exception_event,
    )
    exception_fields = _exception_payload_fields(event, is_exception_event=is_exception_event)
    affected_machine = resource_identities["affected_machine"]
    affected_operator = resource_identities["affected_operator"]
    return {
        "event_id": getattr(event, "id", None),
        "op_id": getattr(event, "op_id", None),
        "schedule_id": getattr(event, "schedule_id", None),
        "action": action,
        "action_label": _execution_action_label(action),
        "event_time": getattr(event, "event_time", None),
        "created_by": getattr(event, "created_by", None),
        "remark": remark,
        "reason_code": getattr(event, "reason_code", None),
        "reason_label": (
            exception_reason_label(getattr(event, "reason_code", None))
            if getattr(event, "reason_code", None)
            else None
        ),
        "severity": getattr(event, "severity", None),
        "severity_label": severity_label(getattr(event, "severity", None)) if getattr(event, "severity", None) else None,
        "impact_minutes": getattr(event, "impact_minutes", None),
        "impact_minutes_label": exception_fields["impact_minutes_label"],
        **_resource_payload("actual_machine_", actual_machine),
        **_resource_payload("actual_operator_", actual_operator),
        **_resource_payload("affected_machine_", affected_machine),
        **_resource_payload("affected_operator_", affected_operator),
        "handling_status_label": exception_fields["handling_status_label"],
        "suggest_reschedule_label": exception_fields["suggest_reschedule_label"],
    }


def execution_result_payload(result: Any, task_card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": event_payload(result.event, result.state),
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
