from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.shared.strict_parse import is_int

EXECUTION_STATUS_NOT_STARTED = "not_started"
EXECUTION_STATUS_COMPLETED = "completed"

_EVENT_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


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


def parse_positive_execution_int(value: Any, field: str) -> int:
    """Plan identity from a SQLite INTEGER column: an exact positive int; text, REAL or bool is corrupt."""
    if not is_int(value) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def required_execution_text(value: Any, field: str) -> str:
    """Required text in the execution storage contract: stripped, and blank is corrupt."""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


@dataclass(frozen=True)
class OperationExecutionScope:
    schedule_version: int
    schedule_id: int
    op_id: int
    batch_id: str
    source_table: str
    effective_plan_role: str

    @classmethod
    def from_values(
        cls,
        *,
        schedule_version: Any,
        schedule_id: Any,
        op_id: Any,
        batch_id: Any,
        source_table: Any,
        effective_plan_role: Any,
    ) -> OperationExecutionScope:
        return cls(
            schedule_version=parse_positive_execution_int(schedule_version, "schedule_version"),
            schedule_id=parse_positive_execution_int(schedule_id, "schedule_id"),
            op_id=parse_positive_execution_int(op_id, "op_id"),
            batch_id=required_execution_text(batch_id, "batch_id"),
            source_table=required_execution_text(source_table, "source_table"),
            effective_plan_role=required_execution_text(effective_plan_role, "effective_plan_role"),
        )


__all__ = [
    "EXECUTION_STATUS_COMPLETED",
    "EXECUTION_STATUS_NOT_STARTED",
    "OperationExecutionScope",
    "parse_operation_event_time",
    "parse_positive_execution_int",
    "required_execution_text",
]
