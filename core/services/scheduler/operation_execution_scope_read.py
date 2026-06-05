from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.models.operation_execution_scope import OperationExecutionScope, parse_positive_execution_int
from core.models.operation_execution_state import OperationExecutionState

from .resource_dispatch_execution_enrichment import apply_execution_state_to_row, row_op_id


def _value(source: Any, name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = parse_positive_execution_int(value, "execution_scope")
    except ValueError:
        return None
    return parsed


def _field(fields: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        value = fields.get(name)
        if value not in (None, ""):
            return value
    return default


def _missing_scope_fields(
    *,
    op_id: Optional[int],
    schedule_id: Optional[int],
    schedule_version: Optional[int],
    batch_id: str,
) -> List[str]:
    missing: List[str] = []
    if op_id is None:
        missing.append("op_id")
    if schedule_id is None:
        missing.append("schedule_id")
    if schedule_version is None:
        missing.append("version")
    if not batch_id:
        missing.append("batch_id")
    return missing


def scope_from_plan_row(row: Any, plan_fields: Mapping[str, Any]) -> OperationExecutionScope:
    op_id = _positive_int(_value(row, "op_id"))
    schedule_id = _positive_int(_value(row, "schedule_id"))
    schedule_version = _positive_int(_value(row, "version"))
    batch_id = _text(_value(row, "batch_id"))
    missing = _missing_scope_fields(
        op_id=op_id,
        schedule_id=schedule_id,
        schedule_version=schedule_version,
        batch_id=batch_id,
    )
    if missing:
        raise ValueError(f"计划行缺少现场执行身份字段：{', '.join(missing)}")
    return OperationExecutionScope.from_values(
        schedule_version=schedule_version,
        schedule_id=schedule_id,
        op_id=op_id,
        batch_id=batch_id,
        source_table=_field(plan_fields, "source_table"),
        effective_plan_role=_field(
            plan_fields,
            "effective_plan_role",
            "selected_role",
        ),
        scenario_id=_field(plan_fields, "scenario_id", default=None),
    )


def scopes_by_op_id_for_plan_rows(
    rows: Sequence[Any],
    plan_fields: Mapping[str, Any],
) -> Dict[int, OperationExecutionScope]:
    scopes_by_op_id: Dict[int, OperationExecutionScope] = {}
    for row in rows or []:
        scope = scope_from_plan_row(row, plan_fields)
        existing = scopes_by_op_id.get(int(scope.op_id))
        if existing is not None and existing != scope:
            raise ValueError(f"工序 {int(scope.op_id)} 对应多个现场执行身份，不能按 op_id 合并读取。")
        scopes_by_op_id[int(scope.op_id)] = scope
    return scopes_by_op_id


def scope_from_feedback_context(context: Any) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=getattr(context, "schedule_version", None),
        schedule_id=getattr(context, "schedule_id", None),
        op_id=getattr(context, "op_id", None),
        batch_id=getattr(context, "batch_id", None),
        source_table=getattr(context, "source_table", None),
        effective_plan_role=getattr(context, "effective_plan_role", None),
        scenario_id=getattr(context, "scenario_id", None),
    )


def scope_from_task_ref(task: Any) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=getattr(task, "schedule_version", None),
        schedule_id=getattr(task, "schedule_id", None),
        op_id=getattr(task, "op_id", None),
        batch_id=getattr(task, "batch_id", None),
        source_table=getattr(task, "source_table", None),
        effective_plan_role=getattr(task, "effective_plan_role", None),
        scenario_id=getattr(task, "scenario_id", None),
    )


def states_by_op_id_for_plan_rows(
    feedback_service: Any,
    rows: Sequence[Any],
    plan_fields: Mapping[str, Any],
) -> Dict[int, OperationExecutionState]:
    scopes_by_op_id = scopes_by_op_id_for_plan_rows(rows, plan_fields)
    states_by_scope = feedback_service.get_execution_state_for_scopes(list(scopes_by_op_id.values()))
    return {
        op_id: states_by_scope[scope]
        for op_id, scope in scopes_by_op_id.items()
        if scope in states_by_scope
    }


def apply_scoped_execution_state_to_rows(
    feedback_service: Any,
    rows: List[Dict[str, Any]],
    plan_fields: Mapping[str, Any],
) -> None:
    states = states_by_op_id_for_plan_rows(feedback_service, rows, plan_fields)
    for row in rows:
        op_id = row_op_id(row)
        state = states.get(op_id) if op_id is not None else None
        if state is not None:
            apply_execution_state_to_row(row, state)


def state_for_feedback_context(feedback_service: Any, context: Any) -> OperationExecutionState:
    scope = scope_from_feedback_context(context)
    return feedback_service.get_execution_state_for_scopes([scope])[scope]


def state_for_task_ref(feedback_service: Any, task: Any) -> OperationExecutionState:
    scope = scope_from_task_ref(task)
    return feedback_service.get_execution_state_for_scopes([scope])[scope]


def events_for_scope(feedback_service: Any, scope: OperationExecutionScope) -> List[Any]:
    return feedback_service.list_execution_events_for_scope(scope)


def events_for_task_ref(feedback_service: Any, task: Any) -> List[Any]:
    return events_for_scope(feedback_service, scope_from_task_ref(task))


__all__ = [
    "apply_scoped_execution_state_to_rows",
    "events_for_scope",
    "events_for_task_ref",
    "scope_from_feedback_context",
    "scope_from_plan_row",
    "scope_from_task_ref",
    "scopes_by_op_id_for_plan_rows",
    "state_for_feedback_context",
    "state_for_task_ref",
    "states_by_op_id_for_plan_rows",
]
