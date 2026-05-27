from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int

EXECUTION_EVENT_START = "start"
EXECUTION_EVENT_PAUSE = "pause"
EXECUTION_EVENT_RESUME = "resume"
EXECUTION_EVENT_FINISH = "finish"
EXECUTION_EVENT_EXCEPTION = "exception"
EXECUTION_ACTION_REPORT_EXCEPTION = "report_exception"

EXECUTION_STATUS_NOT_STARTED = "not_started"
EXECUTION_STATUS_PROCESSING = "processing"
EXECUTION_STATUS_PAUSED = "paused"
EXECUTION_STATUS_EXCEPTION = "exception"
EXECUTION_STATUS_COMPLETED = "completed"

VALID_EXECUTION_EVENT_TYPES = (
    EXECUTION_EVENT_START,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_EXCEPTION,
)

VALID_EXECUTION_ACTIONS = (
    EXECUTION_EVENT_START,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_FINISH,
    EXECUTION_ACTION_REPORT_EXCEPTION,
)

VALID_REPORTED_STATUSES = (
    EXECUTION_STATUS_PROCESSING,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_COMPLETED,
)


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


@dataclass(frozen=True)
class OperationExecutionEvent:
    id: Optional[int]
    schedule_version: int
    schedule_id: int
    op_id: int
    batch_id: str
    event_type: str
    reported_status: str
    event_time: str
    source_table: str = "schedule"
    effective_plan_role: str = "adopted"
    scenario_id: Optional[str] = None
    actual_machine_id: Optional[str] = None
    actual_operator_id: Optional[str] = None
    quantity_done: Optional[int] = None
    quantity_scrapped: Optional[int] = None
    reason_code: Optional[str] = None
    reason_detail: Optional[str] = None
    severity: Optional[str] = None
    impact_minutes: Optional[int] = None
    affected_machine_id: Optional[str] = None
    affected_operator_id: Optional[str] = None
    handling_status: Optional[str] = None
    suggest_reschedule: Optional[str] = None
    remark: Optional[str] = None
    created_by: Optional[str] = None
    idempotency_key: Optional[str] = None
    request_fingerprint: Optional[str] = None
    previous_state_revision: str = ""
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OperationExecutionEvent:
        return cls(
            id=parse_int(get(row, "id"), default=None),
            schedule_version=parse_int(get(row, "schedule_version"), default=0) or 0,
            schedule_id=parse_int(get(row, "schedule_id"), default=0) or 0,
            op_id=parse_int(get(row, "op_id"), default=0) or 0,
            batch_id=str(get(row, "batch_id") or ""),
            source_table=str(get(row, "source_table") or "schedule"),
            effective_plan_role=str(get(row, "effective_plan_role") or "adopted"),
            scenario_id=_text_or_none(get(row, "scenario_id")),
            event_type=str(get(row, "event_type") or ""),
            reported_status=str(get(row, "reported_status") or ""),
            event_time=str(get(row, "event_time") or ""),
            actual_machine_id=_text_or_none(get(row, "actual_machine_id")),
            actual_operator_id=_text_or_none(get(row, "actual_operator_id")),
            quantity_done=parse_int(get(row, "quantity_done"), default=None),
            quantity_scrapped=parse_int(get(row, "quantity_scrapped"), default=None),
            reason_code=_text_or_none(get(row, "reason_code")),
            reason_detail=_text_or_none(get(row, "reason_detail")),
            severity=_text_or_none(get(row, "severity")),
            impact_minutes=parse_int(get(row, "impact_minutes"), default=None),
            affected_machine_id=_text_or_none(get(row, "affected_machine_id")),
            affected_operator_id=_text_or_none(get(row, "affected_operator_id")),
            handling_status=_text_or_none(get(row, "handling_status")),
            suggest_reschedule=_text_or_none(get(row, "suggest_reschedule")),
            remark=_text_or_none(get(row, "remark")),
            created_by=_text_or_none(get(row, "created_by")),
            idempotency_key=_text_or_none(get(row, "idempotency_key")),
            request_fingerprint=_text_or_none(get(row, "request_fingerprint")),
            previous_state_revision=str(get(row, "previous_state_revision") or ""),
            created_at=_text_or_none(get(row, "created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)


__all__ = [
    "EXECUTION_ACTION_REPORT_EXCEPTION",
    "EXECUTION_EVENT_EXCEPTION",
    "EXECUTION_EVENT_FINISH",
    "EXECUTION_EVENT_PAUSE",
    "EXECUTION_EVENT_RESUME",
    "EXECUTION_EVENT_START",
    "EXECUTION_STATUS_COMPLETED",
    "EXECUTION_STATUS_EXCEPTION",
    "EXECUTION_STATUS_NOT_STARTED",
    "EXECUTION_STATUS_PAUSED",
    "EXECUTION_STATUS_PROCESSING",
    "OperationExecutionEvent",
    "VALID_EXECUTION_ACTIONS",
    "VALID_EXECUTION_EVENT_TYPES",
    "VALID_REPORTED_STATUSES",
]
