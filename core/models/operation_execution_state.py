from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .operation_execution_event import EXECUTION_STATUS_NOT_STARTED


@dataclass(frozen=True)
class OperationExecutionState:
    op_id: int
    batch_id: Optional[str]
    current_status: str = EXECUTION_STATUS_NOT_STARTED
    current_status_label: str = "待开工"
    actual_start_time: Optional[str] = None
    actual_end_time: Optional[str] = None
    actual_duration_minutes: Optional[float] = None
    pause_duration_minutes: float = 0.0
    actual_machine_id: Optional[str] = None
    actual_machine_name: Optional[str] = None
    actual_machine_display_label: Optional[str] = None
    actual_machine_identity_label: Optional[str] = None
    actual_machine_label: Optional[str] = None
    actual_operator_id: Optional[str] = None
    actual_operator_name: Optional[str] = None
    actual_operator_display_label: Optional[str] = None
    actual_operator_identity_label: Optional[str] = None
    actual_operator_label: Optional[str] = None
    last_event_id: Optional[int] = None
    last_event_type: Optional[str] = None
    last_event_time: Optional[str] = None
    last_event_action_label: Optional[str] = None
    last_event_remark: Optional[str] = None
    latest_exception_event_id: Optional[int] = None
    latest_exception_time: Optional[str] = None
    latest_exception_reason_code: Optional[str] = None
    latest_exception_reason_label: Optional[str] = None
    latest_exception_severity: Optional[str] = None
    latest_exception_severity_label: Optional[str] = None
    latest_exception_impact_minutes: Optional[int] = None
    latest_exception_impact_minutes_label: Optional[str] = None
    latest_exception_affected_machine_id: Optional[str] = None
    latest_exception_affected_machine_name: Optional[str] = None
    latest_exception_affected_machine_display_label: Optional[str] = None
    latest_exception_affected_machine_identity_label: Optional[str] = None
    latest_exception_affected_machine_label: Optional[str] = None
    latest_exception_affected_operator_id: Optional[str] = None
    latest_exception_affected_operator_name: Optional[str] = None
    latest_exception_affected_operator_display_label: Optional[str] = None
    latest_exception_affected_operator_identity_label: Optional[str] = None
    latest_exception_affected_operator_label: Optional[str] = None
    latest_exception_handling_status: Optional[str] = None
    latest_exception_handling_status_label: Optional[str] = None
    latest_exception_suggest_reschedule: bool = False
    latest_exception_suggest_reschedule_label: Optional[str] = None
    latest_exception_remark: Optional[str] = None
    state_revision: str = ""
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


__all__ = ["OperationExecutionState"]
