from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
    REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE,
    OperationExecutionEvent,
    parse_operation_event_time,
)
from core.models.operation_execution_labels import (
    HANDLING_STATUS_LABELS,
    REASON_LABELS,
    SEVERITY_LABELS,
    action_to_event_type,
    event_type_to_action,
    execution_action_label,
)
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.operation_execution_state import OperationExecutionState
from core.shared.field_labels import display_field_label


@dataclass(frozen=True)
class ExecutionFeedbackContext:
    schedule_version: int
    schedule_id: int
    op_id: int
    batch_id: str
    expected_state_revision: str
    created_by: str
    idempotency_key: str
    requested_plan_role: str
    source_table: str
    effective_plan_role: str
    scenario_id: Optional[str] = None


@dataclass(frozen=True)
class ExecutionFeedbackResult:
    event: OperationExecutionEvent
    state: OperationExecutionState
    idempotency_reused: bool
    state_revision: str


def _scope_for_context(context: ExecutionFeedbackContext) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=context.schedule_version,
        schedule_id=context.schedule_id,
        op_id=context.op_id,
        batch_id=context.batch_id,
        source_table=context.source_table,
        effective_plan_role=context.effective_plan_role,
        scenario_id=context.scenario_id,
    )


def _state_for_context(event_repo: Any, context: ExecutionFeedbackContext) -> OperationExecutionState:
    scope = _scope_for_context(context)
    return event_repo.aggregate_states_by_scopes([scope])[scope]


_REPORTED_STATUS_BY_ACTION = {
    action: REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE[action_to_event_type(action)]
    for action in (
        EXECUTION_EVENT_START,
        EXECUTION_EVENT_RESUME,
        EXECUTION_EVENT_PAUSE,
        EXECUTION_ACTION_REPORT_EXCEPTION,
        EXECUTION_EVENT_FINISH,
    )
}

_ACTION_PAYLOAD_FIELDS = (
    "event_time",
    "actual_machine_id",
    "actual_operator_id",
    "quantity_done",
    "quantity_scrapped",
    "reason_code",
    "reason_detail",
    "severity",
    "impact_minutes",
    "affected_machine_id",
    "affected_operator_id",
    "handling_status",
    "suggest_reschedule",
    "remark",
)

_PUBLIC_REASON_MESSAGES = {
    "idempotency_conflict": "这次提交和刚才的重复提交标记不一致，系统已拒绝写入，请刷新后重试。",
    "stale_state_revision": "页面上的现场状态已经不是最新，请刷新后再提交。",
    "not_current_official_plan": "当前不是最新正式采用方案，不能写现场记录。",
    "schedule_mismatch": "排程记录和当前正式计划对不上，请刷新后重试。",
    "invalid_state_transition": "当前现场状态不允许执行这个操作，请刷新页面查看最新状态；如果现场记录有误，请联系计划员处理。",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> Optional[str]:
    text = _text(value)
    return text or None


def _required_text(value: Any, field: str) -> str:
    text = _text(value)
    if not text:
        field_label = _feedback_field_label(field)
        raise ValidationError(
            f"{field_label}不能为空，请填写后再提交。",
            field=field,
            details={"reason": "missing_required_field", "field": field, "field_label": field_label},
        )
    return text


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError
        sign = text[0] if text[0] in ("+", "-") else ""
        digits = text[1:] if sign else text
        if not digits.isdigit():
            raise ValueError
        return int(text)
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    raise ValueError


def _invalid_field_value(field: str, message: Optional[str] = None) -> ValidationError:
    field_label = _feedback_field_label(field)
    return ValidationError(
        message or f"{field_label}填写不正确，请检查后重试。",
        field=field,
        details={"reason": "invalid_field_value", "field": field, "field_label": field_label},
    )


def _positive_int(value: Any, field: str) -> int:
    try:
        parsed = _parse_int(value)
    except ValueError:
        raise _invalid_field_value(field) from None
    if parsed <= 0:
        raise _invalid_field_value(field)
    return parsed


def _optional_int(value: Any, field: str) -> Optional[int]:
    if value is None or _text(value) == "":
        return None
    try:
        parsed = _parse_int(value)
    except ValueError:
        raise _invalid_field_value(field) from None
    return parsed


def _optional_non_negative_int(value: Any, field: str) -> Optional[int]:
    if value is None or _text(value) == "":
        return None
    return _non_negative_int(value, field)


def _feedback_field_label(field: str) -> str:
    if field == "operator_id":
        return "操作人员"
    return display_field_label(field)


def _required_non_negative_int(value: Any, field: str) -> int:
    if value is None or _text(value) == "":
        field_label = _feedback_field_label(field)
        raise ValidationError(
            f"{field_label}不能为空，请填写后再提交。",
            field=field,
            details={"reason": "missing_required_field", "field": field, "field_label": field_label},
        )
    return _non_negative_int(value, field)


def _non_negative_int(value: Any, field: str) -> int:
    try:
        parsed = _parse_int(value)
    except ValueError:
        raise _invalid_field_value(field) from None
    if parsed < 0:
        raise _invalid_field_value(field)
    return parsed


def _conflict(reason: str, *, details: Optional[Dict[str, Any]] = None, message: Optional[str] = None) -> AppError:
    payload = {"reason": reason}
    if details:
        payload.update(details)
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        message or _PUBLIC_REASON_MESSAGES.get(reason) or "现场反馈提交失败，请刷新后重试。",
        details=payload,
    )


def _parse_feedback_datetime(value: Any, field: str = "event_time") -> datetime:
    try:
        return parse_operation_event_time(value)
    except ValueError:
        raise _invalid_field_value(field, "反馈时间格式不正确，请检查后再提交。") from None


def _normalize_feedback_datetime(value: Any, field: str = "event_time") -> str:
    return _parse_feedback_datetime(value, field).strftime("%Y-%m-%d %H:%M:%S")


def _validate_known_value(value: Optional[str], field: str, labels: Dict[str, str]) -> None:
    if value is None:
        return
    if value not in labels:
        raise _invalid_field_value(field)


def _event_public_tuple(event: OperationExecutionEvent) -> Tuple[Any, ...]:
    return (
        event.schedule_version,
        event.schedule_id,
        event.op_id,
        event.batch_id,
        event.source_table,
        event.effective_plan_role,
        event.scenario_id,
        event.event_type,
        event.reported_status,
        event.event_time,
        event.actual_machine_id,
        event.actual_operator_id,
        event.quantity_done,
        event.quantity_scrapped,
        event.reason_code,
        event.reason_detail,
        event.severity,
        event.impact_minutes,
        event.affected_machine_id,
        event.affected_operator_id,
        event.handling_status,
        event.suggest_reschedule,
        event.remark,
        event.created_by,
        event.previous_state_revision,
    )
