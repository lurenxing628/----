from __future__ import annotations

import sqlite3

import pytest
from operation_execution_migration_support import connect_legacy_v17_execution_schema

from core.infrastructure.migrations import v18


def _connect() -> sqlite3.Connection:
    return connect_legacy_v17_execution_schema(
        schedule_ids=(100, 101),
        operation_ids=(10,),
    )


def _insert_event(
    conn: sqlite3.Connection,
    *,
    version: int,
    schedule_id: int,
    key: str,
    event_type: str = "start",
    reported_status: str = "processing",
) -> None:
    conn.execute(
        """
        INSERT INTO OperationExecutionEvents(
            schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
            scenario_id, event_type, reported_status, event_time, created_by,
            idempotency_key, request_fingerprint, previous_state_revision
        )
        VALUES (?, ?, 10, 'B1', 'schedule', 'adopted', NULL, ?, ?,
                '2026-05-01 08:00:00', 'pytest', ?, ?, '10:0:0')
        """,
        (int(version), int(schedule_id), event_type, reported_status, key, f"{key}-fingerprint"),
    )


def _index_columns(conn: sqlite3.Connection, name: str) -> list:
    return [str(row["name"]) for row in conn.execute(f"PRAGMA index_info({name})").fetchall()]


def test_v18_migrates_state_revision_unique_constraint_to_plan_scope() -> None:
    conn = _connect()
    try:
        _insert_event(conn, version=1, schedule_id=100, key="legacy-v17")
        v18.run(conn)

        assert _index_columns(conn, "idx_operation_execution_events_op_revision_unique") == [
            "schedule_version",
            "schedule_id",
            "op_id",
            "previous_state_revision",
        ]
        _insert_event(conn, version=2, schedule_id=101, key="same-op-revision-other-plan")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_event(conn, version=1, schedule_id=100, key="same-op-revision-same-plan")
    finally:
        conn.close()


def test_v18_rejects_invalid_event_sequence_before_rebuild() -> None:
    conn = _connect()
    try:
        _insert_event(
            conn,
            version=1,
            schedule_id=100,
            key="finish-without-start",
            event_type="finish",
            reported_status="completed",
        )

        with pytest.raises(RuntimeError, match="事件流顺序不合法"):
            v18.run(conn)
    finally:
        conn.close()
