from __future__ import annotations

import sqlite3
from typing import Iterable

from core.infrastructure.migrations import v13, v14, v15, v16, v17


def connect_legacy_v17_execution_schema(
    *,
    schedule_ids: Iterable[int],
    operation_ids: Iterable[int],
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    prepare_legacy_v17_execution_schema(conn, schedule_ids=schedule_ids, operation_ids=operation_ids)
    return conn


def prepare_legacy_v17_execution_schema(
    conn: sqlite3.Connection,
    *,
    schedule_ids: Iterable[int],
    operation_ids: Iterable[int],
) -> None:
    _create_parent_tables(conn, schedule_ids=schedule_ids, operation_ids=operation_ids)
    for migration in (v13, v14, v15, v16, v17):
        migration.run(conn)


def _create_parent_tables(
    conn: sqlite3.Connection,
    *,
    schedule_ids: Iterable[int],
    operation_ids: Iterable[int],
) -> None:
    conn.executescript(
        """
        CREATE TABLE Schedule(id INTEGER PRIMARY KEY, version INTEGER NOT NULL, op_id INTEGER NOT NULL);
        CREATE TABLE BatchOperations(id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL);
        CREATE TABLE Machines(machine_id TEXT PRIMARY KEY);
        CREATE TABLE Operators(operator_id TEXT PRIMARY KEY);
        CREATE UNIQUE INDEX idx_schedule_identity_unique ON Schedule(id, version, op_id);
        CREATE UNIQUE INDEX idx_batch_operations_identity_unique ON BatchOperations(id, batch_id);
        """
    )
    schedule_id_list = [int(item) for item in schedule_ids]
    operation_id_list = [int(item) for item in operation_ids]
    op_id = operation_id_list[0] if operation_id_list else 0
    conn.executemany(
        "INSERT INTO Schedule(id, version, op_id) VALUES (?, ?, ?)",
        [(item, offset + 1, op_id) for offset, item in enumerate(schedule_id_list)],
    )
    conn.executemany("INSERT INTO BatchOperations(id, batch_id) VALUES (?, ?)", [(item, "B1") for item in operation_id_list])
