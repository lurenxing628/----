from __future__ import annotations

from typing import Optional, Sequence

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
    "CAST(b.due_date AS TEXT) AS due_date",
    "b.priority AS priority",
    "m.name AS machine_name",
    "o.name AS operator_name",
    "sup.name AS supplier_name",
)

_COMMON_JOINS = (
    "LEFT JOIN BatchOperations bo ON bo.id = s.op_id",
    "LEFT JOIN Batches b ON b.batch_id = bo.batch_id",
    "LEFT JOIN Machines m ON m.machine_id = s.machine_id",
    "LEFT JOIN Operators o ON o.operator_id = s.operator_id",
    "LEFT JOIN Suppliers sup ON sup.supplier_id = bo.supplier_id",
)


def build_schedule_detail_sql(
    *,
    where_clauses: Sequence[str],
    plan_rows_cte_sql: Optional[str] = None,
) -> str:
    columns_sql = ",\n            ".join(_COMMON_DETAIL_COLUMNS)
    joins_sql = "\n        ".join(_COMMON_JOINS)
    where_sql = "\n          AND ".join(where_clauses)
    from_sql = "Schedule s"
    cte_sql = ""
    if plan_rows_cte_sql is not None:
        cte_sql = f"""
        WITH plan_rows AS (
            {plan_rows_cte_sql.strip()}
        )
        """
        from_sql = "plan_rows s"

    return f"""
        {cte_sql}
        SELECT
            {columns_sql}
        FROM {from_sql}
        {joins_sql}
        WHERE {where_sql}
        ORDER BY s.start_time, s.id
        """
