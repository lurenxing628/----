from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_NOT_STARTED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
    OperationExecutionEvent,
)
from core.models.operation_execution_labels import (
    event_type_to_action,
    exception_reason_label,
    execution_action_label,
    execution_status_label,
    handling_status_label,
    severity_label,
    suggest_reschedule_label,
)
from core.models.operation_execution_state import OperationExecutionState

_REPORTED_STATUS_BY_EVENT_TYPE = {
    EXECUTION_EVENT_START: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_RESUME: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_PAUSE: EXECUTION_STATUS_PAUSED,
    EXECUTION_EVENT_EXCEPTION: EXECUTION_STATUS_EXCEPTION,
    EXECUTION_EVENT_FINISH: EXECUTION_STATUS_COMPLETED,
}


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _duration_minutes(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return None
    return round((end_dt - start_dt).total_seconds() / 60.0, 6)


def _impact_minutes_label(value: Optional[int]) -> str:
    if value is None:
        return "暂时不知道影响多久"
    return f"预计影响 {int(value)} 分钟"


def _suggest_reschedule_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "yes", "true")


def _current_status(last_event: OperationExecutionEvent) -> str:
    return last_event.reported_status or _REPORTED_STATUS_BY_EVENT_TYPE.get(
        last_event.event_type, EXECUTION_STATUS_NOT_STARTED
    )


def _event_remark(event: OperationExecutionEvent) -> Optional[str]:
    return event.remark or event.reason_detail


def _latest_exception(events: Sequence[OperationExecutionEvent]) -> Optional[OperationExecutionEvent]:
    for event in reversed(events):
        if event.event_type == EXECUTION_EVENT_EXCEPTION:
            return event
    return None


def _first_event_time(events: Sequence[OperationExecutionEvent], event_type: str) -> Optional[str]:
    for event in events:
        if event.event_type == event_type:
            return event.event_time
    return None


def _last_event_time(events: Sequence[OperationExecutionEvent], event_type: str) -> Optional[str]:
    for event in reversed(events):
        if event.event_type == event_type:
            return event.event_time
    return None


def _last_text(events: Sequence[OperationExecutionEvent], field: str) -> Optional[str]:
    for event in reversed(events):
        value = getattr(event, field)
        if value:
            return str(value)
    return None


def _pause_duration_minutes(events: Sequence[OperationExecutionEvent]) -> float:
    total = 0.0
    pause_started_at: Optional[str] = None
    for event in events:
        if event.event_type == EXECUTION_EVENT_PAUSE:
            pause_started_at = event.event_time
            continue
        if pause_started_at and event.event_type in (
            EXECUTION_EVENT_RESUME,
            EXECUTION_EVENT_FINISH,
            EXECUTION_EVENT_EXCEPTION,
        ):
            minutes = _duration_minutes(pause_started_at, event.event_time)
            if minutes is not None:
                total += float(minutes)
            pause_started_at = None
    return total


def _label(labels: Dict[str, str], value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return labels.get(str(value), str(value))


def _empty_exception_fields() -> Dict[str, Any]:
    return {
        "latest_exception_event_id": None,
        "latest_exception_time": None,
        "latest_exception_reason_code": None,
        "latest_exception_reason_label": None,
        "latest_exception_severity": None,
        "latest_exception_severity_label": None,
        "latest_exception_impact_minutes": None,
        "latest_exception_impact_minutes_label": None,
        "latest_exception_affected_machine_id": None,
        "latest_exception_affected_machine_label": None,
        "latest_exception_affected_operator_id": None,
        "latest_exception_affected_operator_label": None,
        "latest_exception_handling_status": None,
        "latest_exception_handling_status_label": None,
        "latest_exception_suggest_reschedule": False,
        "latest_exception_suggest_reschedule_label": None,
        "latest_exception_remark": None,
    }


def _exception_fields(
    latest_exception: Optional[OperationExecutionEvent],
    *,
    machine_labels: Dict[str, str],
    operator_labels: Dict[str, str],
) -> Dict[str, Any]:
    if latest_exception is None:
        return _empty_exception_fields()
    return {
        "latest_exception_event_id": latest_exception.id,
        "latest_exception_time": latest_exception.event_time,
        "latest_exception_reason_code": latest_exception.reason_code,
        "latest_exception_reason_label": exception_reason_label(latest_exception.reason_code),
        "latest_exception_severity": latest_exception.severity,
        "latest_exception_severity_label": severity_label(latest_exception.severity),
        "latest_exception_impact_minutes": latest_exception.impact_minutes,
        "latest_exception_impact_minutes_label": _impact_minutes_label(latest_exception.impact_minutes),
        "latest_exception_affected_machine_id": latest_exception.affected_machine_id,
        "latest_exception_affected_machine_label": _label(machine_labels, latest_exception.affected_machine_id),
        "latest_exception_affected_operator_id": latest_exception.affected_operator_id,
        "latest_exception_affected_operator_label": _label(operator_labels, latest_exception.affected_operator_id),
        "latest_exception_handling_status": latest_exception.handling_status,
        "latest_exception_handling_status_label": handling_status_label(latest_exception.handling_status),
        "latest_exception_suggest_reschedule": _suggest_reschedule_bool(latest_exception.suggest_reschedule),
        "latest_exception_suggest_reschedule_label": suggest_reschedule_label(latest_exception.suggest_reschedule),
        "latest_exception_remark": _event_remark(latest_exception),
    }


def build_operation_execution_state(
    *,
    op_id: int,
    batch_id: Optional[str],
    events: List[OperationExecutionEvent],
    machine_labels: Dict[str, str],
    operator_labels: Dict[str, str],
) -> OperationExecutionState:
    if not events:
        return OperationExecutionState(
            op_id=int(op_id),
            batch_id=batch_id,
            state_revision=f"{int(op_id)}:0:0",
        )
    last_event = events[-1]
    latest_exception = _latest_exception(events)
    actual_start_time = _first_event_time(events, EXECUTION_EVENT_START)
    actual_end_time = _last_event_time(events, EXECUTION_EVENT_FINISH)
    actual_machine_id = _last_text(events, "actual_machine_id")
    actual_operator_id = _last_text(events, "actual_operator_id")
    current_status = _current_status(last_event)
    return OperationExecutionState(
        op_id=int(op_id),
        batch_id=last_event.batch_id or batch_id,
        current_status=current_status,
        current_status_label=execution_status_label(current_status),
        actual_start_time=actual_start_time,
        actual_end_time=actual_end_time,
        actual_duration_minutes=_duration_minutes(actual_start_time, actual_end_time),
        pause_duration_minutes=_pause_duration_minutes(events),
        actual_machine_id=actual_machine_id,
        actual_machine_label=machine_labels.get(actual_machine_id or "") if actual_machine_id else None,
        actual_operator_id=actual_operator_id,
        actual_operator_label=operator_labels.get(actual_operator_id or "") if actual_operator_id else None,
        last_event_id=last_event.id,
        last_event_type=last_event.event_type,
        last_event_time=last_event.event_time,
        last_event_action_label=execution_action_label(event_type_to_action(last_event.event_type)),
        last_event_remark=_event_remark(last_event),
        **_exception_fields(
            latest_exception,
            machine_labels=machine_labels,
            operator_labels=operator_labels,
        ),
        state_revision=f"{int(op_id)}:{len(events)}:{int(last_event.id or 0)}",
        updated_at=last_event.event_time,
    )


__all__ = ["build_operation_execution_state"]
