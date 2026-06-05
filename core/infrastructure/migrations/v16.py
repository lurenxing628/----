from __future__ import annotations

import sqlite3
from typing import List

from core.infrastructure.operation_execution_event_data_contract import operation_execution_event_sequence_issues
from core.models.operation_execution_event import parse_operation_event_time

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
        return MigrationOutcome.SKIPPED

    _reject_incomplete_legacy_events(conn)
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
    if column == "suggest_reschedule":
        return (
            "CASE LOWER(TRIM(CAST(legacy.suggest_reschedule AS TEXT))) "
            "WHEN '1' THEN 1 WHEN 'yes' THEN 1 WHEN 'true' THEN 1 ELSE 0 END"
        )
    if column == "created_at":
        return "legacy.created_at"
    return f"legacy.{column}"


def _reject_incomplete_legacy_events(conn: sqlite3.Connection) -> None:
    blockers = []
    missing_reason_ids = _legacy_event_ids(conn, _missing_reason_condition())
    if missing_reason_ids:
        blockers.append(f"缺少暂停/异常原因的事件 id={', '.join(missing_reason_ids)}")
    missing_severity_ids = _legacy_event_ids(conn, _missing_exception_severity_condition())
    if missing_severity_ids:
        blockers.append(f"缺少异常严重程度的事件 id={', '.join(missing_severity_ids)}")
    missing_resource_ids = _legacy_event_ids(conn, _missing_resource_condition())
    if missing_resource_ids:
        blockers.append(f"引用了不存在设备或人员的事件 id={', '.join(missing_resource_ids)}")
    bad_reschedule_ids = _legacy_event_ids(conn, _invalid_suggest_reschedule_condition())
    if bad_reschedule_ids:
        blockers.append(f"缺少重排建议或重排建议不是 0/1/yes/no/true/false 的事件 id={', '.join(bad_reschedule_ids)}")
    missing_created_at_ids = _legacy_event_ids(conn, _missing_created_at_condition())
    if missing_created_at_ids:
        blockers.append(f"缺少创建时间的事件 id={', '.join(missing_created_at_ids)}")
    bad_event_time_ids = _invalid_event_time_ids(conn)
    if bad_event_time_ids:
        blockers.append(f"事件时间缺失或格式不正确的事件 id={', '.join(bad_event_time_ids)}")
    bad_status_pair_ids = _legacy_event_ids(conn, _bad_event_status_pair_condition())
    if bad_status_pair_ids:
        blockers.append(f"事件类型和上报状态互相矛盾的事件 id={', '.join(bad_status_pair_ids)}")
    bad_sequence_issues = operation_execution_event_sequence_issues(conn, limit=4)
    if bad_sequence_issues:
        blockers.append(f"事件流顺序不合法：{'；'.join(bad_sequence_issues)}")
    if blockers:
        raise RuntimeError("早期现场事件数据不完整，不能静默补成当前合法事件；请先人工修复后再迁移：" + "；".join(blockers))


def _legacy_event_ids(conn: sqlite3.Connection, condition: str) -> List[str]:
    rows = conn.execute(
        f"""
        SELECT id
        FROM OperationExecutionEvents AS legacy
        WHERE {condition}
        ORDER BY id
        LIMIT 10
        """
    ).fetchall()
    return [str(row["id"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows]


def _missing_reason_condition() -> str:
    return (
        "legacy.event_type IN ('pause', 'exception') "
        "AND (legacy.reason_code IS NULL OR TRIM(legacy.reason_code) = '')"
    )


def _missing_exception_severity_condition() -> str:
    return "legacy.event_type = 'exception' AND (legacy.severity IS NULL OR TRIM(legacy.severity) = '')"


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


def _invalid_suggest_reschedule_condition() -> str:
    return (
        "legacy.suggest_reschedule IS NULL "
        "OR TRIM(CAST(legacy.suggest_reschedule AS TEXT)) = '' "
        "OR LOWER(TRIM(CAST(legacy.suggest_reschedule AS TEXT))) NOT IN ('0', '1', 'no', 'yes', 'false', 'true')"
    )


def _missing_created_at_condition() -> str:
    return "legacy.created_at IS NULL OR TRIM(CAST(legacy.created_at AS TEXT)) = ''"


def _invalid_event_time_ids(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        """
        SELECT id, event_time
        FROM OperationExecutionEvents AS legacy
        ORDER BY id
        """
    ).fetchall()
    bad_ids: List[str] = []
    for row in rows:
        event_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        event_time = row["event_time"] if isinstance(row, sqlite3.Row) else row[1]
        try:
            parse_operation_event_time(event_time)
        except ValueError:
            bad_ids.append(str(event_id))
        if len(bad_ids) >= 10:
            break
    return bad_ids


def _bad_event_status_pair_condition() -> str:
    return (
        "NOT ("
        "(legacy.event_type IN ('start', 'resume') AND legacy.reported_status = 'processing') "
        "OR (legacy.event_type = 'pause' AND legacy.reported_status = 'paused') "
        "OR (legacy.event_type = 'exception' AND legacy.reported_status = 'exception') "
        "OR (legacy.event_type = 'finish' AND legacy.reported_status = 'completed')"
        ")"
    )
