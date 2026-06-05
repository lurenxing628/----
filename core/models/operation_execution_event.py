from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple

from ._helpers import RowLike, as_dict, get, parse_int
from .operation_execution_scope import OperationExecutionScope, validate_current_official_execution_scope

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
    return parse_operation_event_time(value).strftime("%Y-%m-%d %H:%M:%S")


def _required_contract_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def normalize_operation_execution_event_values(
    *,
    event_type: Any,
    reported_status: Any,
    event_time: Any,
) -> Tuple[str, str, str]:
    event_type_text = _required_contract_text(event_type, "event_type")
    if event_type_text not in VALID_EXECUTION_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {VALID_EXECUTION_EVENT_TYPES}: {event_type!r}")
    status_text = _required_contract_text(reported_status, "reported_status")
    if status_text not in VALID_REPORTED_STATUSES:
        raise ValueError(f"reported_status must be one of {VALID_REPORTED_STATUSES}: {reported_status!r}")
    expected_status = REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE[event_type_text]
    if status_text != expected_status:
        raise ValueError(
            f"reported_status {status_text!r} does not match event_type {event_type_text!r}; "
            f"expected {expected_status!r}"
        )
    return event_type_text, status_text, normalize_operation_event_time(event_time)


def _event_field(event: Any, field_name: str) -> Any:
    if hasattr(event, field_name):
        return getattr(event, field_name)
    try:
        return event[field_name]
    except (KeyError, TypeError, IndexError):
        return None


def _event_identity(event: Any) -> str:
    event_id = _event_field(event, "id")
    if event_id not in (None, ""):
        return f"id={event_id}"
    return f"type={_event_field(event, 'event_type')!r}"


def _event_positive_int(event: Any, field_name: str) -> int:
    value = parse_int(_event_field(event, field_name), default=None)
    if value is None or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer at {_event_identity(event)}")
    return value


def _event_scope(event: Any) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=_event_field(event, "schedule_version"),
        schedule_id=_event_field(event, "schedule_id"),
        op_id=_event_field(event, "op_id"),
        batch_id=_event_field(event, "batch_id"),
        source_table=_event_field(event, "source_table"),
        effective_plan_role=_event_field(event, "effective_plan_role"),
        scenario_id=_event_field(event, "scenario_id"),
    )


def _event_id_for_revision(event: Any, *, index: int, total: int) -> int:
    raw = _event_field(event, "id")
    value = parse_int(raw, default=None)
    if value is not None and value > 0:
        return value
    if index < total:
        raise ValueError(f"id is required before following event at {_event_identity(event)}")
    return 0


def _optional_non_negative_int_field(value: Any, field_name: str) -> Optional[int]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    parsed = parse_int(value, default=None)
    if parsed is None:
        raise ValueError(f"{field_name} must be an integer: {value!r}")
    if parsed < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")
    return parsed


def _suggest_reschedule_field(value: Any) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0
    parsed = parse_int(value, default=None)
    if parsed not in (0, 1):
        raise ValueError(f"suggest_reschedule must be 0 or 1: {value!r}")
    return int(parsed)


def validate_operation_execution_event_transition(*, current_status: Any, event_type: Any) -> str:
    status_text = _required_contract_text(current_status, "current_status")
    if status_text not in ALLOWED_EXECUTION_EVENTS_BY_STATUS:
        raise ValueError(f"current_status must be one of {tuple(ALLOWED_EXECUTION_EVENTS_BY_STATUS)}: {current_status!r}")
    event_type_text = _required_contract_text(event_type, "event_type")
    if event_type_text not in VALID_EXECUTION_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {VALID_EXECUTION_EVENT_TYPES}: {event_type!r}")
    allowed_events = ALLOWED_EXECUTION_EVENTS_BY_STATUS[status_text]
    if event_type_text not in allowed_events:
        raise ValueError(
            "operation execution event sequence is invalid: "
            f"event_type {event_type_text!r} cannot follow current_status {status_text!r}"
        )
    return REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE[event_type_text]


def validate_operation_execution_event_sequence(events: Sequence[Any]) -> None:
    current_status = EXECUTION_STATUS_NOT_STARTED
    previous_event_time: Optional[datetime] = None
    previous_event_id = 0
    sequence_scope: Optional[OperationExecutionScope] = None
    events_list = list(events or [])
    for index, event in enumerate(events_list, start=1):
        scope = _event_scope(event)
        if sequence_scope is None:
            sequence_scope = scope
        elif scope != sequence_scope:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"scope changed from {sequence_scope!r} to {scope!r} at {_event_identity(event)}"
            )
        op_id = _event_positive_int(event, "op_id")
        expected_previous_revision = f"{op_id}:{index - 1}:{previous_event_id}"
        previous_revision = _required_contract_text(
            _event_field(event, "previous_state_revision"),
            "previous_state_revision",
        )
        if previous_revision != expected_previous_revision:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"previous_state_revision {previous_revision!r} does not match current state "
                f"{expected_previous_revision!r} at {_event_identity(event)}"
            )
        event_type, reported_status, event_time = normalize_operation_execution_event_values(
            event_type=_event_field(event, "event_type"),
            reported_status=_event_field(event, "reported_status"),
            event_time=_event_field(event, "event_time"),
        )
        validate_operation_execution_event_transition(
            current_status=current_status,
            event_type=event_type,
        )
        parsed_event_time = parse_operation_event_time(event_time)
        if previous_event_time is not None and parsed_event_time < previous_event_time:
            raise ValueError(
                "operation execution event sequence is invalid: "
                f"event_time moved backwards at {_event_identity(event)}"
            )
        previous_event_time = parsed_event_time
        current_status = reported_status
        previous_event_id = _event_id_for_revision(event, index=index, total=len(events_list))


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
    source_table: str
    effective_plan_role: str
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
    suggest_reschedule: int = 0
    remark: Optional[str] = None
    created_by: Optional[str] = None
    idempotency_key: Optional[str] = None
    request_fingerprint: Optional[str] = None
    previous_state_revision: str = ""
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OperationExecutionEvent:
        event_type, reported_status, event_time = normalize_operation_execution_event_values(
            event_type=get(row, "event_type"),
            reported_status=get(row, "reported_status"),
            event_time=get(row, "event_time"),
        )
        scope = OperationExecutionScope.from_values(
            schedule_version=get(row, "schedule_version"),
            schedule_id=get(row, "schedule_id"),
            op_id=get(row, "op_id"),
            batch_id=get(row, "batch_id"),
            source_table=get(row, "source_table"),
            effective_plan_role=get(row, "effective_plan_role"),
            scenario_id=get(row, "scenario_id"),
        )
        source_table, effective_plan_role, scenario_id = validate_current_official_execution_scope(
            source_table=scope.source_table,
            effective_plan_role=scope.effective_plan_role,
            scenario_id=scope.scenario_id,
        )
        return cls(
            id=parse_int(get(row, "id"), default=None),
            schedule_version=scope.schedule_version,
            schedule_id=scope.schedule_id,
            op_id=scope.op_id,
            batch_id=scope.batch_id,
            source_table=source_table,
            effective_plan_role=effective_plan_role,
            scenario_id=scenario_id,
            event_type=event_type,
            reported_status=reported_status,
            event_time=event_time,
            actual_machine_id=_text_or_none(get(row, "actual_machine_id")),
            actual_operator_id=_text_or_none(get(row, "actual_operator_id")),
            quantity_done=_optional_non_negative_int_field(get(row, "quantity_done"), "quantity_done"),
            quantity_scrapped=_optional_non_negative_int_field(get(row, "quantity_scrapped"), "quantity_scrapped"),
            reason_code=_text_or_none(get(row, "reason_code")),
            reason_detail=_text_or_none(get(row, "reason_detail")),
            severity=_text_or_none(get(row, "severity")),
            impact_minutes=_optional_non_negative_int_field(get(row, "impact_minutes"), "impact_minutes"),
            affected_machine_id=_text_or_none(get(row, "affected_machine_id")),
            affected_operator_id=_text_or_none(get(row, "affected_operator_id")),
            handling_status=_text_or_none(get(row, "handling_status")),
            suggest_reschedule=_suggest_reschedule_field(get(row, "suggest_reschedule")),
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
    "ALLOWED_EXECUTION_EVENTS_BY_STATUS",
    "REPORTED_STATUS_BY_EXECUTION_EVENT_TYPE",
    "VALID_EXECUTION_ACTIONS",
    "VALID_EXECUTION_EVENT_TYPES",
    "VALID_REPORTED_STATUSES",
    "normalize_operation_execution_event_values",
    "normalize_operation_event_time",
    "parse_operation_event_time",
    "validate_operation_execution_event_sequence",
    "validate_operation_execution_event_transition",
]
