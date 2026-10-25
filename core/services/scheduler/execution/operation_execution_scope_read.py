from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from core.models.operation_execution_scope import OperationExecutionScope


def scope_from_plan_row(row: Mapping[str, Any], plan_fields: Mapping[str, Any]) -> OperationExecutionScope:
    # 计划行是 SQLite 原始行，身份字段只在 from_values 里校验一次；坏值抛 ValueError。
    return OperationExecutionScope.from_values(
        schedule_version=row["version"],
        schedule_id=row["schedule_id"],
        op_id=row["op_id"],
        batch_id=row["batch_id"],
        source_table=plan_fields["source_table"],
        effective_plan_role=plan_fields["effective_plan_role"],
        scenario_id=plan_fields["scenario_id"],
    )


def scopes_by_op_id_for_plan_rows(
    rows: Sequence[Mapping[str, Any]],
    plan_fields: Mapping[str, Any],
) -> Dict[int, OperationExecutionScope]:
    scopes_by_op_id: Dict[int, OperationExecutionScope] = {}
    for row in rows:
        scope = scope_from_plan_row(row, plan_fields)
        existing = scopes_by_op_id.get(scope.op_id)
        if existing is not None and existing != scope:
            raise ValueError(f"工序 {scope.op_id} 对应多个现场执行身份，不能按 op_id 合并读取。")
        scopes_by_op_id[scope.op_id] = scope
    return scopes_by_op_id


__all__ = [
    "scope_from_plan_row",
    "scopes_by_op_id_for_plan_rows",
]
