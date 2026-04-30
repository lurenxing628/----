from __future__ import annotations

from typing import List, Sequence

_COMMON_DETAIL_COLUMNS = (
    "s.id AS schedule_id",
    "s.op_id AS op_id",
    "s.start_time AS start_time",
    "s.end_time AS end_time",
    "s.lock_status AS lock_status",
    "s.version AS version",
    "bo.op_code AS op_code",
    "bo.batch_id AS batch_id",
    "bo.piece_id AS piece_id",
    "bo.seq AS seq",
    "bo.op_type_name AS op_type_name",
    "bo.source AS source",
    "bo.status AS op_status",
    "s.machine_id AS machine_id",
    "s.operator_id AS operator_id",
    "bo.supplier_id AS supplier_id",
    "b.part_no AS part_no",
    "b.part_name AS part_name",
    "b.due_date AS due_date",
    "b.priority AS priority",
    "m.name AS machine_name",
    "o.name AS operator_name",
    "sup.name AS supplier_name",
)

_DISPATCH_DETAIL_COLUMNS = (
    "s.id AS schedule_id",
    "s.op_id AS op_id",
    "s.start_time AS start_time",
    "s.end_time AS end_time",
    "s.lock_status AS lock_status",
    "s.version AS version",
    "bo.op_code AS op_code",
    "bo.batch_id AS batch_id",
    "bo.piece_id AS piece_id",
    "bo.seq AS seq",
    "bo.op_type_name AS op_type_name",
    "bo.source AS source",
    "bo.status AS op_status",
    "bo.supplier_id AS supplier_id",
    "b.part_no AS part_no",
    "b.part_name AS part_name",
    "b.due_date AS due_date",
    "b.priority AS priority",
    "s.machine_id AS machine_id",
    "m.name AS machine_name",
    "m.team_id AS machine_team_id",
    "mt.name AS machine_team_name",
    "s.operator_id AS operator_id",
    "o.name AS operator_name",
    "o.team_id AS operator_team_id",
    "ot.name AS operator_team_name",
    "sup.name AS supplier_name",
)

_COMMON_JOINS = (
    "LEFT JOIN BatchOperations bo ON bo.id = s.op_id",
    "LEFT JOIN Batches b ON b.batch_id = bo.batch_id",
    "LEFT JOIN Machines m ON m.machine_id = s.machine_id",
    "LEFT JOIN Operators o ON o.operator_id = s.operator_id",
    "LEFT JOIN Suppliers sup ON sup.supplier_id = bo.supplier_id",
)

_DISPATCH_JOINS = (
    "LEFT JOIN BatchOperations bo ON bo.id = s.op_id",
    "LEFT JOIN Batches b ON b.batch_id = bo.batch_id",
    "LEFT JOIN Machines m ON m.machine_id = s.machine_id",
    "LEFT JOIN ResourceTeams mt ON mt.team_id = m.team_id",
    "LEFT JOIN Operators o ON o.operator_id = s.operator_id",
    "LEFT JOIN ResourceTeams ot ON ot.team_id = o.team_id",
    "LEFT JOIN Suppliers sup ON sup.supplier_id = bo.supplier_id",
)


def _select_columns(*, include_team_context: bool) -> List[str]:
    if include_team_context:
        return list(_DISPATCH_DETAIL_COLUMNS)
    return list(_COMMON_DETAIL_COLUMNS)


def _join_clauses(*, include_team_context: bool) -> List[str]:
    if include_team_context:
        return list(_DISPATCH_JOINS)
    return list(_COMMON_JOINS)


def build_schedule_detail_sql(
    *,
    where_clauses: Sequence[str],
    include_team_context: bool = False,
) -> str:
    if not where_clauses:
        raise ValueError("where_clauses is required")

    columns_sql = ",\n            ".join(_select_columns(include_team_context=include_team_context))
    joins_sql = "\n        ".join(_join_clauses(include_team_context=include_team_context))
    where_sql = "\n          AND ".join(where_clauses)

    return f"""
        SELECT
            {columns_sql}
        FROM Schedule s
        {joins_sql}
        WHERE {where_sql}
        ORDER BY s.start_time, s.id
        """
