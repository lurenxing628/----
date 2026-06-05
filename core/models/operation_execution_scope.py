from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE


def parse_positive_execution_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(value, int):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text.isdigit():
            raise ValueError(f"{field} must be a positive integer")
        parsed = int(text)
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def validate_current_official_execution_scope(
    *,
    source_table: Any,
    effective_plan_role: Any,
    scenario_id: Any = None,
) -> Tuple[str, str, Optional[str]]:
    source = _required_text(source_table, "source_table")
    if source != SOURCE_SCHEDULE:
        raise ValueError("operation execution events must belong to current official schedule rows")
    role = _required_text(effective_plan_role, "effective_plan_role")
    if role != ROLE_ADOPTED:
        raise ValueError("operation execution events must belong to adopted plan")
    scenario = _optional_text(scenario_id)
    if scenario is not None:
        raise ValueError("operation execution events cannot belong to scenario preview plans")
    return source, role, scenario


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
            batch_id=_required_text(batch_id, "batch_id"),
            source_table=_required_text(source_table, "source_table"),
            effective_plan_role=_required_text(effective_plan_role, "effective_plan_role"),
            scenario_id=_optional_text(scenario_id),
        )


def operation_execution_scope_from_event(event: Any) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=getattr(event, "schedule_version", None),
        schedule_id=getattr(event, "schedule_id", None),
        op_id=getattr(event, "op_id", None),
        batch_id=getattr(event, "batch_id", None),
        source_table=getattr(event, "source_table", None),
        effective_plan_role=getattr(event, "effective_plan_role", None),
        scenario_id=getattr(event, "scenario_id", None),
    )


__all__ = [
    "OperationExecutionScope",
    "operation_execution_scope_from_event",
    "parse_positive_execution_int",
    "validate_current_official_execution_scope",
]
