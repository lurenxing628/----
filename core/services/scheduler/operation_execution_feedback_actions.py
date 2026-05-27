from __future__ import annotations

from typing import Any, Dict, Protocol, Sequence, Tuple, cast

from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
    OperationExecutionEvent,
)

from .operation_execution_feedback_support import ExecutionFeedbackContext, ExecutionFeedbackResult, _text


class _FeedbackActionsHost(Protocol):
    machine_repo: Any
    operator_repo: Any

    def record_event(self, context: ExecutionFeedbackContext, *, action: str, **payload: Any) -> ExecutionFeedbackResult:
        ...


class OperationExecutionFeedbackActionsMixin:
    def resource_labels_for_events(self, events: Sequence[OperationExecutionEvent]) -> Tuple[Dict[str, str], Dict[str, str]]:
        machine_ids = sorted(
            {
                _text(getattr(event, "affected_machine_id", None))
                for event in events
                if _text(getattr(event, "affected_machine_id", None))
            }
        )
        operator_ids = sorted(
            {
                _text(getattr(event, "affected_operator_id", None))
                for event in events
                if _text(getattr(event, "affected_operator_id", None))
            }
        )
        machine_labels: Dict[str, str] = {}
        operator_labels: Dict[str, str] = {}
        host = cast(_FeedbackActionsHost, self)
        for machine_id in machine_ids:
            machine = host.machine_repo.get(machine_id)
            machine_labels[machine_id] = str(getattr(machine, "name", "") or machine_id) if machine else machine_id
        for operator_id in operator_ids:
            operator = host.operator_repo.get(operator_id)
            operator_labels[operator_id] = str(getattr(operator, "name", "") or operator_id) if operator else operator_id
        return machine_labels, operator_labels

    def start_operation(
        self,
        context: ExecutionFeedbackContext,
        *,
        event_time: Any,
        operator_id: Any,
        machine_id: Any,
        remark: Any = None,
    ) -> ExecutionFeedbackResult:
        return cast(_FeedbackActionsHost, self).record_event(
            context,
            action=EXECUTION_EVENT_START,
            event_time=event_time,
            actual_operator_id=operator_id,
            actual_machine_id=machine_id,
            remark=remark,
        )

    def finish_operation(
        self,
        context: ExecutionFeedbackContext,
        *,
        event_time: Any,
        quantity_done: Any = None,
        quantity_scrapped: Any = None,
        remark: Any = None,
    ) -> ExecutionFeedbackResult:
        return cast(_FeedbackActionsHost, self).record_event(
            context,
            action=EXECUTION_EVENT_FINISH,
            event_time=event_time,
            quantity_done=quantity_done,
            quantity_scrapped=quantity_scrapped,
            remark=remark,
        )

    def pause_operation(self, context: ExecutionFeedbackContext, *, event_time: Any, reason_code: Any, remark: Any = None):
        return cast(_FeedbackActionsHost, self).record_event(
            context,
            action=EXECUTION_EVENT_PAUSE,
            event_time=event_time,
            reason_code=reason_code,
            remark=remark,
        )

    def resume_operation(self, context: ExecutionFeedbackContext, *, event_time: Any, remark: Any = None):
        return cast(_FeedbackActionsHost, self).record_event(
            context,
            action=EXECUTION_EVENT_RESUME,
            event_time=event_time,
            remark=remark,
        )

    def report_exception(
        self,
        context: ExecutionFeedbackContext,
        *,
        event_time: Any,
        reason_code: Any,
        severity: Any,
        impact_minutes: Any = None,
        affected_machine_id: Any = None,
        affected_operator_id: Any = None,
        handling_status: Any = "new",
        suggest_reschedule: Any = None,
        remark: Any = None,
        reason_detail: Any = None,
    ) -> ExecutionFeedbackResult:
        return cast(_FeedbackActionsHost, self).record_event(
            context,
            action=EXECUTION_ACTION_REPORT_EXCEPTION,
            event_time=event_time,
            reason_code=reason_code,
            reason_detail=reason_detail,
            severity=severity,
            impact_minutes=impact_minutes,
            affected_machine_id=affected_machine_id,
            affected_operator_id=affected_operator_id,
            handling_status=handling_status,
            suggest_reschedule=suggest_reschedule,
            remark=remark,
        )
