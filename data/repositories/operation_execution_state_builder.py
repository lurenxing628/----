from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_START,
    EXECUTION_STATUS_NOT_STARTED,
    OperationExecutionEvent,
)


@dataclass(frozen=True)
class OperationExecutionEventFold:
    batch_id: Optional[str]
    current_status: str
    actual_start_time: Optional[str]
    actual_end_time: Optional[str]
    actual_machine_id: Optional[str]
    actual_operator_id: Optional[str]
    state_revision: str
    latest_exception: Optional[OperationExecutionEvent]


def fold_operation_execution_events(
    *, op_id: int, batch_id: Optional[str], events: Sequence[OperationExecutionEvent],
) -> OperationExecutionEventFold:
    """Fold validated scope events without resource labels or UI state."""
    start, finish, machine, operator, exception = None, None, None, None, None
    for event in events:
        if event.event_type == EXECUTION_EVENT_START and start is None:
            start = event.event_time
        elif event.event_type == EXECUTION_EVENT_FINISH:
            finish = event.event_time
        elif event.event_type == EXECUTION_EVENT_EXCEPTION:
            exception = event
        if event.actual_machine_id:
            machine = event.actual_machine_id
        if event.actual_operator_id:
            operator = event.actual_operator_id
    last = events[-1] if events else None
    return OperationExecutionEventFold(
        batch_id=batch_id if last is None else last.batch_id,
        current_status=EXECUTION_STATUS_NOT_STARTED if last is None else last.reported_status,
        actual_start_time=start, actual_end_time=finish,
        actual_machine_id=machine, actual_operator_id=operator,
        state_revision=f"{op_id}:{len(events)}:{0 if last is None else last.id}",
        latest_exception=exception,
    )


__all__ = ["OperationExecutionEventFold", "fold_operation_execution_events"]
