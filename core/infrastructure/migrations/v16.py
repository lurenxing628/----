from __future__ import annotations

import sqlite3
from typing import List

from .common import MigrationOutcome
from .v15 import _EVENT_INDEX_SQL, _EVENT_TABLE_SQL

_EVENT_COLUMNS: List[str] = [
    "id",
    "schedule_version",
    "schedule_id",
    "op_id",
    "batch_id",
    "source_table",
    "effective_plan_role",
    "scenario_id",
    "event_type",
    "reported_status",
    "event_time",
    "actual_machine_id",
    "actual_operator_id",
    "quantity_done",
    "quantity_scrapped",
    "reason_code",
    "reason_detail",
    "severity",
    "impact_minutes",
    "affected_machine_id",
    "affected_operator_id",
    "handling_status",
    "suggest_reschedule",
    "remark",
    "created_by",
    "idempotency_key",
    "request_fingerprint",
    "previous_state_revision",
    "created_at",
]


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v16 迁移：修正已经跑过早期 v15 的执行事件表结构。
    """
    if not _table_exists(conn, "OperationExecutionEvents"):
        _create_current_event_table(conn)
        return MigrationOutcome.APPLIED

    _drop_event_indexes(conn)
    conn.execute("ALTER TABLE OperationExecutionEvents RENAME TO OperationExecutionEvents_v15_backup")
    _create_current_event_table(conn)
    _copy_legacy_events(conn)
    conn.execute("DROP TABLE OperationExecutionEvents_v15_backup")
    return MigrationOutcome.APPLIED


def _create_current_event_table(conn: sqlite3.Connection) -> None:
    conn.execute(_EVENT_TABLE_SQL)
    for sql in _EVENT_INDEX_SQL:
        conn.execute(sql)


def _drop_event_indexes(conn: sqlite3.Connection) -> None:
    for name in (
        "idx_operation_execution_events_latest_exception",
        "idx_operation_execution_events_op_revision_unique",
        "idx_operation_execution_events_batch",
        "idx_operation_execution_events_schedule_op",
        "idx_operation_execution_events_schedule",
        "idx_operation_execution_events_op",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {name}")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _copy_legacy_events(conn: sqlite3.Connection) -> None:
    columns = ", ".join(_EVENT_COLUMNS)
    select_columns = ", ".join(_legacy_select_expr(column) for column in _EVENT_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO OperationExecutionEvents ({columns})
        SELECT {select_columns}
        FROM OperationExecutionEvents_v15_backup AS legacy
        ORDER BY id ASC
        """
    )


def _legacy_select_expr(column: str) -> str:
    if column == "reason_code":
        return (
            "CASE WHEN legacy.event_type IN ('pause', 'exception') "
            "AND (legacy.reason_code IS NULL OR TRIM(legacy.reason_code) = '') "
            "THEN 'other' ELSE legacy.reason_code END"
        )
    if column == "reason_detail":
        return _append_legacy_note(
            _append_legacy_note(
                "legacy.reason_detail",
                _missing_reason_condition(),
                "迁移补齐：早期现场事件缺少原因，已按“其他”保留原事件。",
            ),
            _missing_exception_severity_condition(),
            "迁移补齐：早期异常事件缺少严重程度，已按“中等”保留原事件。",
        )
    if column == "severity":
        return (
            "CASE WHEN "
            + _missing_exception_severity_condition()
            + " THEN 'medium' ELSE legacy.severity END"
        )
    if column == "actual_machine_id":
        return _existing_resource_or_null("legacy.actual_machine_id", "Machines", "machine_id")
    if column == "actual_operator_id":
        return _existing_resource_or_null("legacy.actual_operator_id", "Operators", "operator_id")
    if column == "affected_machine_id":
        return _existing_resource_or_null("legacy.affected_machine_id", "Machines", "machine_id")
    if column == "affected_operator_id":
        return _existing_resource_or_null("legacy.affected_operator_id", "Operators", "operator_id")
    if column == "suggest_reschedule":
        return (
            "CASE LOWER(TRIM(CAST(legacy.suggest_reschedule AS TEXT))) "
            "WHEN '1' THEN 1 WHEN 'yes' THEN 1 WHEN 'true' THEN 1 ELSE 0 END"
        )
    if column == "remark":
        return _append_legacy_note(
            "legacy.remark",
            _missing_resource_condition(),
            "迁移补齐：早期现场事件引用的设备或人员已不存在，已保留事件并清空失效资源引用。",
        )
    if column == "created_at":
        return "COALESCE(legacy.created_at, CURRENT_TIMESTAMP)"
    return f"legacy.{column}"


def _missing_reason_condition() -> str:
    return (
        "legacy.event_type IN ('pause', 'exception') "
        "AND (legacy.reason_code IS NULL OR TRIM(legacy.reason_code) = '')"
    )


def _missing_exception_severity_condition() -> str:
    return "legacy.event_type = 'exception' AND (legacy.severity IS NULL OR TRIM(legacy.severity) = '')"


def _append_legacy_note(value_expr: str, condition: str, note: str) -> str:
    escaped_note = note.replace("'", "''")
    return (
        f"CASE WHEN {condition} THEN "
        f"CASE WHEN {value_expr} IS NULL OR TRIM({value_expr}) = '' "
        f"THEN '{escaped_note}' ELSE {value_expr} || '；{escaped_note}' END "
        f"ELSE {value_expr} END"
    )


def _existing_resource_or_null(value_expr: str, table_name: str, column_name: str) -> str:
    return (
        f"CASE WHEN {value_expr} IS NULL OR TRIM({value_expr}) = '' THEN NULL "
        f"WHEN EXISTS (SELECT 1 FROM {table_name} WHERE {column_name} = {value_expr}) "
        f"THEN {value_expr} ELSE NULL END"
    )


def _missing_resource_condition() -> str:
    checks = (
        ("legacy.actual_machine_id", "Machines", "machine_id"),
        ("legacy.affected_machine_id", "Machines", "machine_id"),
        ("legacy.actual_operator_id", "Operators", "operator_id"),
        ("legacy.affected_operator_id", "Operators", "operator_id"),
    )
    parts = []
    for value_expr, table_name, column_name in checks:
        parts.append(
            f"({value_expr} IS NOT NULL AND TRIM({value_expr}) <> '' "
            f"AND NOT EXISTS (SELECT 1 FROM {table_name} WHERE {column_name} = {value_expr}))"
        )
    return " OR ".join(parts)
