from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from core.models.operation_execution_event import (
    OPERATION_EXECUTION_EVENT_COLUMNS,
    OperationExecutionEvent,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import (
    OperationExecutionScope,
    operation_execution_scope_from_event,
)

from .base_repo import BaseRepository

_EVENT_COLUMNS_SQL = ", ".join(OPERATION_EXECUTION_EVENT_COLUMNS)


def _scope_where(scope: OperationExecutionScope) -> Tuple[str, Tuple[Any, ...]]:
    params = (
        scope.schedule_version,
        scope.schedule_id,
        scope.op_id,
        scope.batch_id,
        scope.source_table,
        scope.effective_plan_role,
    )
    sql = (
        "schedule_version = ? AND schedule_id = ? AND op_id = ? AND batch_id = ? "
        "AND source_table = ? AND effective_plan_role = ?"
    )
    if scope.scenario_id is None:
        return f"({sql} AND scenario_id IS NULL)", params
    return f"({sql} AND scenario_id = ?)", params + (scope.scenario_id,)


def _validate_events_by_scope(
    events: Sequence[OperationExecutionEvent],
) -> Dict[OperationExecutionScope, List[OperationExecutionEvent]]:
    grouped: Dict[OperationExecutionScope, List[OperationExecutionEvent]] = {}
    for event in events:
        grouped.setdefault(operation_execution_scope_from_event(event), []).append(event)
    for scoped_events in grouped.values():
        validate_operation_execution_event_sequence(scoped_events)
    return grouped


class OperationExecutionEventRepo(BaseRepository):
    """按完整计划身份读取历史现场执行事件。"""

    def list_events_by_scopes(
        self, scopes: Sequence[OperationExecutionScope]
    ) -> Dict[OperationExecutionScope, List[OperationExecutionEvent]]:
        if not scopes:
            return {}
        out: List[OperationExecutionEvent] = []
        for i in range(0, len(scopes), 80):
            chunk = scopes[i : i + 80]
            clauses: List[str] = []
            params: List[Any] = []
            for scope in chunk:
                clause, scope_params = _scope_where(scope)
                clauses.append(clause)
                params.extend(scope_params)
            rows = self.fetchall(
                f"""
                SELECT {_EVENT_COLUMNS_SQL}
                FROM OperationExecutionEvents
                WHERE {" OR ".join(clauses)}
                ORDER BY schedule_version ASC, schedule_id ASC, op_id ASC, id ASC
                """,
                tuple(params),
            )
            out.extend(OperationExecutionEvent.from_row(row) for row in rows)
        return _validate_events_by_scope(out)


__all__ = ["OperationExecutionEventRepo"]
