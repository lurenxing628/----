from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from core.shared.strict_parse import integer_value, is_blank_input

from ._helpers import RowLike
from .operation_execution_scope import (
    OperationExecutionScope,
    operation_execution_scope_from_event,
    required_execution_text,
    validate_current_official_execution_scope,
)

EXECUTION_EVENT_START = "start"
EXECUTION_EVENT_PAUSE = "pause"
EXECUTION_EVENT_RESUME = "resume"
EXECUTION_EVENT_FINISH = "finish"
EXECUTION_EVENT_EXCEPTION = "exception"

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

VALID_REPORTED_STATUSES = (
    EXECUTION_STATUS_PROCESSING,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_COMPLETED,
)

REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE = {
    EXECUTION_EVENT_START: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_RESUME: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_PAUSE: EXECUTION_STATUS_PAUSED,
    EXECUTION_EVENT_EXCEPTION: EXECUTION_STATUS_EXCEPTION,
    EXECUTION_EVENT_FINISH: EXECUTION_STATUS_COMPLETED,
}

ALLOWED_EXECUTION_EVENTS_BY_STATUS = {
    EXECUTION_STATUS_NOT_STARTED: frozenset((EXECUTION_EVENT_START,)),
    EXECUTION_STATUS_PROCESSING: frozenset((EXECUTION_EVENT_PAUSE, EXECUTION_EVENT_FINISH, EXECUTION_EVENT_EXCEPTION)),
    EXECUTION_STATUS_PAUSED: frozenset((EXECUTION_EVENT_RESUME, EXECUTION_EVENT_FINISH, EXECUTION_EVENT_EXCEPTION)),
    EXECUTION_STATUS_EXCEPTION: frozenset((EXECUTION_EVENT_RESUME, EXECUTION_EVENT_FINISH)),
    EXECUTION_STATUS_COMPLETED: frozenset(),
}

_EVENT_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


def _event_time_text(value: Any) -> str:
    return str(value or "").strip().replace("/", "-").replace("T", " ").replace("：", ":")


def parse_operation_event_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    text = _event_time_text(value)
    if not text:
        raise ValueError("event_time is required")
    for fmt in _EVENT_TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"event_time must be a valid datetime: {value!r}")


def normalize_operation_event_time(value: Any) -> str:
    return parse_operation_event_time(value).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def normalize_operation_execution_event_values(
    *,
    event_type: Any,
    reported_status: Any,
    event_time: Any,
) -> Tuple[str, str, str]:
    event_type_text = required_execution_text(event_type, "event_type")
    if event_type_text not in VALID_EXECUTION_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {VALID_EXECUTION_EVENT_TYPES}: {event_type!r}")
    status_text = required_execution_text(reported_status, "reported_status")
    if status_text not in VALID_REPORTED_STATUSES:
        raise ValueError(f"reported_status must be one of {VALID_REPORTED_STATUSES}: {reported_status!r}")
    expected_status = REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE[event_type_text]
    if status_text != expected_status:
        raise ValueError(
            f"reported_status {status_text!r} does not match event_type {event_type_text!r}; "
            f"expected {expected_status!r}"
        )
    return event_type_text, status_text, normalize_operation_event_time(event_time)


def _event_identity(event: OperationExecutionEventSequenceEntry) -> str:
    if event.id is not None:
        return f"id={event.id}"
    return f"type={event.event_type!r}"


def _event_id_for_revision(event: OperationExecutionEventSequenceEntry) -> int:
    # from_row 已把 id 读成整数或 None（非整数）；这里只判断能否作为状态版本里的事件编号。
    if event.id is None or event.id <= 0:
        raise ValueError(f"id must be a positive integer at {_event_identity(event)}")
    return event.id


def _optional_non_negative_int_field(value: Any, field_name: str) -> Optional[int]:
    if is_blank_input(value):
        return None
    parsed = integer_value(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be an integer: {value!r}")
    if parsed < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")
    return parsed


def _suggest_reschedule_field(value: Any) -> int:
    if is_blank_input(value):
        return 0
    parsed = integer_value(value)
    if parsed not in (0, 1):
        raise ValueError(f"suggest_reschedule must be 0 or 1: {value!r}")
    return int(parsed)


def _next_execution_status(current_status: str, event_type: str) -> str:
    if event_type not in ALLOWED_EXECUTION_EVENTS_BY_STATUS[current_status]:
        raise ValueError(
            "operation execution event sequence is invalid: "
            f"event_type {event_type!r} cannot follow current_status {current_status!r}"
        )
    return REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE[event_type]


def validate_operation_execution_event_sequence(events: Iterable[OperationExecutionEventSequenceEntry]) -> None:
    current_status = EXECUTION_STATUS_NOT_STARTED
    previous_event_time: Optional[str] = None
    previous_event_id = 0
    sequence_scope: Optional[OperationExecutionScope] = None
    for index, event in enumerate(events, start=1):
        scope = operation_execution_scope_from_event(event)
        if sequence_scope is None:
            sequence_scope = scope
        elif scope != sequence_scope:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"scope changed from {sequence_scope!r} to {scope!r} at {_event_identity(event)}"
            )
        expected_previous_revision = f"{event.op_id}:{index - 1}:{previous_event_id}"
        previous_revision = event.previous_state_revision
        if previous_revision != expected_previous_revision:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"previous_state_revision {previous_revision!r} does not match current state "
                f"{expected_previous_revision!r} at {_event_identity(event)}"
            )
        _next_execution_status(current_status, event.event_type)
        if previous_event_time is not None and event.event_time < previous_event_time:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"event_time moved backwards at {_event_identity(event)}"
            )
        previous_event_time = event.event_time
        current_status = event.reported_status
        previous_event_id = _event_id_for_revision(event)


OPERATION_EXECUTION_EVENT_SEQUENCE_COLUMNS = (
    "id",
    "schedule_version",
    "schedule_id",
    "op_id",
    "batch_id",
    "source_table",
    "effective_plan_role",
    "scenario_id",
    "event_type",
    "reported_status",
    "event_time",
    "previous_state_revision",
)
OPERATION_EXECUTION_EVENT_COLUMNS = OPERATION_EXECUTION_EVENT_SEQUENCE_COLUMNS[:-1] + (
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
    "created_by",
    "idempotency_key",
    "request_fingerprint",
    "previous_state_revision",
    "created_at",
)


def _sequence_values(row: RowLike) -> Dict[str, Any]:
    event_type, reported_status, event_time = normalize_operation_execution_event_values(
        event_type=row["event_type"],
        reported_status=row["reported_status"],
        event_time=row["event_time"],
    )
    scope = OperationExecutionScope.from_values(
        schedule_version=row["schedule_version"],
        schedule_id=row["schedule_id"],
        op_id=row["op_id"],
        batch_id=row["batch_id"],
        source_table=row["source_table"],
        effective_plan_role=row["effective_plan_role"],
        scenario_id=row["scenario_id"],
    )
    validate_current_official_execution_scope(scope)
    return {
        # 非整数 id 读作 None，由顺序校验 _event_id_for_revision 按事件身份报错。
        "id": integer_value(row["id"]),
        "schedule_version": scope.schedule_version,
        "schedule_id": scope.schedule_id,
        "op_id": scope.op_id,
        "batch_id": scope.batch_id,
        "source_table": scope.source_table,
        "effective_plan_role": scope.effective_plan_role,
        "scenario_id": scope.scenario_id,
        "event_type": event_type,
        "reported_status": reported_status,
        "event_time": event_time,
        "previous_state_revision": required_execution_text(row["previous_state_revision"], "previous_state_revision"),
    }


@dataclass(frozen=True)
class OperationExecutionEventSequenceEntry:
    """顺序校验只需要的 12 列：归属、事件类型与状态、时间和前一状态版本。"""

    id: Optional[int]
    schedule_version: int
    schedule_id: int
    op_id: int
    batch_id: str
    event_type: str
    reported_status: str
    event_time: str
    source_table: str
    effective_plan_role: str
    scenario_id: Optional[str]
    previous_state_revision: str

    @classmethod
    def from_row(cls, row: RowLike) -> OperationExecutionEventSequenceEntry:
        return cls(**_sequence_values(row))


@dataclass(frozen=True)
class OperationExecutionEvent(OperationExecutionEventSequenceEntry):
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
    suggest_reschedule: int = 0
    remark: Optional[str] = None
    created_by: Optional[str] = None
    idempotency_key: Optional[str] = None
    request_fingerprint: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OperationExecutionEvent:
        return cls(
            **_sequence_values(row),
            actual_machine_id=_text_or_none(row["actual_machine_id"]),
            actual_operator_id=_text_or_none(row["actual_operator_id"]),
            quantity_done=_optional_non_negative_int_field(row["quantity_done"], "quantity_done"),
            quantity_scrapped=_optional_non_negative_int_field(row["quantity_scrapped"], "quantity_scrapped"),
            reason_code=_text_or_none(row["reason_code"]),
            reason_detail=_text_or_none(row["reason_detail"]),
            severity=_text_or_none(row["severity"]),
            impact_minutes=_optional_non_negative_int_field(row["impact_minutes"], "impact_minutes"),
            affected_machine_id=_text_or_none(row["affected_machine_id"]),
            affected_operator_id=_text_or_none(row["affected_operator_id"]),
            handling_status=_text_or_none(row["handling_status"]),
            suggest_reschedule=_suggest_reschedule_field(row["suggest_reschedule"]),
            remark=_text_or_none(row["remark"]),
            created_by=_text_or_none(row["created_by"]),
            idempotency_key=_text_or_none(row["idempotency_key"]),
            request_fingerprint=_text_or_none(row["request_fingerprint"]),
            created_at=_text_or_none(row["created_at"]),
        )


__all__ = [
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
    "OPERATION_EXECUTION_EVENT_COLUMNS",
    "OPERATION_EXECUTION_EVENT_SEQUENCE_COLUMNS",
    "OperationExecutionEvent",
    "OperationExecutionEventSequenceEntry",
    "ALLOWED_EXECUTION_EVENTS_BY_STATUS",
    "REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE",
    "VALID_EXECUTION_EVENT_TYPES",
    "VALID_REPORTED_STATUSES",
    "normalize_operation_execution_event_values",
    "normalize_operation_event_time",
    "parse_operation_event_time",
    "validate_operation_execution_event_sequence",
]
