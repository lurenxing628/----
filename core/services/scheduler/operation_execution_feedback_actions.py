from __future__ import annotations

from typing import Any, Protocol, cast

from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
)

from .operation_execution_feedback_support import ExecutionFeedbackContext, ExecutionFeedbackResult


class _FeedbackActionsHost(Protocol):
    def record_event(self, context: ExecutionFeedbackContext, *, action: str, **payload: Any) -> ExecutionFeedbackResult:
        ...


class OperationExecutionFeedbackActionsMixin:
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
