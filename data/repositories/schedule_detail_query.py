from __future__ import annotations

from typing import Sequence

_COMMON_DETAIL_COLUMNS = (
    "s.task_ref AS task_ref",
    "s.op_id AS op_id",
    "s.operation_ref AS operation_ref",
    "s.start_time AS start_time",
    "s.end_time AS end_time",
    "s.start_us AS start_us",
    "s.end_us AS end_us",
    "s.is_point_event AS is_point_event",
    "bo.op_code AS op_code",
    "s.batch_id AS batch_id",
    "s.op_type_name AS op_type_name",
    "s.source AS source",
    "s.machine_id AS machine_id",
    "s.operator_id AS operator_id",
    "m.name AS machine_name",
    "o.name AS operator_name",
)

_COMMON_JOINS = (
    "JOIN BatchOperations bo ON bo.id = s.op_id",
    "LEFT JOIN Machines m ON m.machine_id = s.machine_id",
    "LEFT JOIN Operators o ON o.operator_id = s.operator_id",
)


def build_schedule_detail_sql(
    *,
    where_clauses: Sequence[str],
) -> str:
    columns_sql = ",\n            ".join(_COMMON_DETAIL_COLUMNS)
    joins_sql = "\n        ".join(_COMMON_JOINS)
    where_sql = "\n          AND ".join(where_clauses)
    return f"""
        SELECT
            {columns_sql}
        FROM Schedule s
        {joins_sql}
        WHERE {where_sql}
        ORDER BY s.start_us ASC, s.id ASC
        """
