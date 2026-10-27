from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.shared.strict_parse import is_int


def parse_positive_execution_int(value: Any, field: str) -> int:
    """Plan identity from a SQLite INTEGER column: an exact positive int; text, REAL or bool is corrupt."""
    if not is_int(value) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def required_execution_text(value: Any, field: str) -> str:
    """Required text in the execution-event storage contract: stripped, and blank is corrupt."""
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
    scenario_id: Optional[str] = None

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
        scenario_id: Any = None,
    ) -> OperationExecutionScope:
        return cls(
            schedule_version=parse_positive_execution_int(schedule_version, "schedule_version"),
            schedule_id=parse_positive_execution_int(schedule_id, "schedule_id"),
            op_id=parse_positive_execution_int(op_id, "op_id"),
            batch_id=required_execution_text(batch_id, "batch_id"),
            source_table=required_execution_text(source_table, "source_table"),
            effective_plan_role=required_execution_text(effective_plan_role, "effective_plan_role"),
            # scenario_id 是只许 NULL 的列（schema CHECK），按原值保留，由正式计划校验判 is not None。
            scenario_id=scenario_id,
        )


def validate_current_official_execution_scope(scope: OperationExecutionScope) -> None:
    """Execution events belong only to the adopted official plan; from_values already normalized the text fields."""
    if scope.source_table != SOURCE_SCHEDULE:
        raise ValueError("operation execution events must belong to current official schedule rows")
    if scope.effective_plan_role != ROLE_ADOPTED:
        raise ValueError("operation execution events must belong to adopted plan")
    if scope.scenario_id is not None:
        raise ValueError("operation execution events cannot belong to scenario preview plans")


def operation_execution_scope_from_event(event: Any) -> OperationExecutionScope:
    return OperationExecutionScope(
        schedule_version=event.schedule_version,
        schedule_id=event.schedule_id,
        op_id=event.op_id,
        batch_id=event.batch_id,
        source_table=event.source_table,
        effective_plan_role=event.effective_plan_role,
        scenario_id=event.scenario_id,
    )


__all__ = [
    "OperationExecutionScope",
    "operation_execution_scope_from_event",
    "parse_positive_execution_int",
    "required_execution_text",
    "validate_current_official_execution_scope",
]
