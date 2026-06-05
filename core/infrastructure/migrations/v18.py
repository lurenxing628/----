from __future__ import annotations

import sqlite3

from core.infrastructure.operation_execution_event_data_contract import operation_execution_event_sequence_issues

from .common import MigrationOutcome, table_exists
from .v15 import _EVENT_INDEX_SQL as _V15_EVENT_INDEX_SQL
from .v15 import _EVENT_TABLE_SQL as _V15_EVENT_TABLE_SQL
from .v16 import _EVENT_COLUMNS, _drop_event_indexes

_EVENT_TABLE_SQL = _V15_EVENT_TABLE_SQL.replace(
    "UNIQUE(op_id, previous_state_revision)",
    "UNIQUE(schedule_version, schedule_id, op_id, previous_state_revision)",
)

_EVENT_INDEX_SQL = tuple(
    sql.replace(
        "OperationExecutionEvents(op_id, previous_state_revision)",
        "OperationExecutionEvents(schedule_version, schedule_id, op_id, previous_state_revision)",
    )
    for sql in _V15_EVENT_INDEX_SQL
)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v18 迁移：现场执行事件的状态修订号唯一性改为按计划身份隔离。
    """
    if not table_exists(conn, "OperationExecutionEvents"):
        return MigrationOutcome.SKIPPED

    _reject_invalid_event_sequences(conn)
    _drop_event_indexes(conn)
    conn.execute("ALTER TABLE OperationExecutionEvents RENAME TO OperationExecutionEvents_v17_backup")
    _create_current_event_table(conn)
    _copy_events(conn)
    conn.execute("DROP TABLE OperationExecutionEvents_v17_backup")
    return MigrationOutcome.APPLIED


def _create_current_event_table(conn: sqlite3.Connection) -> None:
    conn.execute(_EVENT_TABLE_SQL)
    for sql in _EVENT_INDEX_SQL:
        conn.execute(sql)


def _copy_events(conn: sqlite3.Connection) -> None:
    columns = ", ".join(_EVENT_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO OperationExecutionEvents ({columns})
        SELECT {columns}
        FROM OperationExecutionEvents_v17_backup
        ORDER BY id ASC
        """
    )


def _reject_invalid_event_sequences(conn: sqlite3.Connection) -> None:
    issues = operation_execution_event_sequence_issues(conn, limit=4)
    if issues:
        raise RuntimeError("现场执行事件流顺序不合法，不能静默迁移；请先人工修复后再迁移：" + "；".join(issues))
