"""回归测试：migrations.v19 收紧 OperationExecutionEvents 计划身份契约——抹掉 source_table/effective_plan_role 默认值、把唯一索引扩展到含 schedule_version/schedule_id/source_table/effective_plan_role/previous_state_revision 的全身份范围（重复触发 IntegrityError、缺身份字段被拒），且 rebuild 前校验事件流顺序合法（finish 先于 start 抛「事件流顺序不合法」）；并验证 ensure_schema/migration_runner 对「SchemaVersion 已是当前版本但残留 v18 默认值/缺表/稀疏壳」的陈旧库 fail-fast 抛 MigrationContractError 而不静默放行或建表。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from operation_execution_migration_support import (
    connect_legacy_v17_execution_schema,
    prepare_legacy_v17_execution_schema,
)

from core.infrastructure import migration_runner
from core.infrastructure.database import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    ensure_schema,
    get_connection,
)
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations import v18, v19
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect() -> sqlite3.Connection:
    conn = connect_legacy_v17_execution_schema(
        schedule_ids=(100, 101),
        operation_ids=(10,),
    )
    v18.run(conn)
    return conn


def _insert_event(
    conn: sqlite3.Connection,
    *,
    batch_id: str = "B1",
    event_type: str = "start",
    key: str,
    revision: str = "10:0:0",
    reported_status: str = "processing",
    schedule_version: int = 1,
    schedule_id: int = 100,
) -> None:
    conn.execute(
        """
        INSERT INTO OperationExecutionEvents(
            schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
            scenario_id, event_type, reported_status, event_time, created_by,
            idempotency_key, request_fingerprint, previous_state_revision
        )
        VALUES (?, ?, 10, ?, 'schedule', 'adopted', NULL, ?, ?,
                '2026-05-01 08:00:00', 'pytest', ?, ?, ?)
        """,
        (int(schedule_version), int(schedule_id), batch_id, event_type, reported_status, key, f"{key}-fingerprint", revision),
    )


def _index_columns(conn: sqlite3.Connection, name: str) -> list:
    return [str(row["name"]) for row in conn.execute(f"PRAGMA index_info({name})").fetchall()]


def _column_default(conn: sqlite3.Connection, name: str):
    for row in conn.execute("PRAGMA table_info(OperationExecutionEvents)").fetchall():
        if str(row["name"]) == name:
            return row["dflt_value"]
    raise AssertionError(f"missing column {name}")


def _create_schema_version_shell(db_path: Path, version: int) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute("INSERT INTO SchemaVersion(id, version) VALUES (1, ?)", (int(version),))
        conn.commit()
    finally:
        conn.close()


def _user_table_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type='table'
              AND name <> 'SchemaVersion'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def _assert_current_contract_error(exc: Exception, expected_issue=None) -> None:
    message = str(exc)
    assert f"SchemaVersion={CURRENT_SCHEMA_VERSION} 等于当前程序支持版本 {CURRENT_SCHEMA_VERSION}" in message
    assert "陈旧结构静默冒充当前版本" in message
    if expected_issue is not None:
        assert expected_issue in message, message


def test_v19_removes_plan_identity_defaults_and_extends_revision_scope() -> None:
    conn = _connect()
    try:
        _insert_event(conn, key="legacy-v18")
        v19.run(conn)

        assert _column_default(conn, "source_table") is None
        assert _column_default(conn, "effective_plan_role") is None
        assert _index_columns(conn, "idx_operation_execution_events_op_revision_unique") == [
            "schedule_version",
            "schedule_id",
            "op_id",
            "batch_id",
            "source_table",
            "effective_plan_role",
            "previous_state_revision",
        ]
        _insert_event(conn, key="same-revision-other-plan", schedule_version=2, schedule_id=101)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_event(conn, key="same-full-scope", revision="10:0:0")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, event_type, reported_status,
                    event_time, created_by, idempotency_key, request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B3', 'start', 'processing', '2026-05-01 08:05:00',
                        'pytest', 'missing-identity', 'missing-identity-fingerprint', '10:0:missing')
                """
            )
    finally:
        conn.close()


def test_v19_rejects_invalid_event_sequence_before_rebuild() -> None:
    conn = _connect()
    try:
        _insert_event(
            conn,
            key="finish-without-start",
            event_type="finish",
            reported_status="completed",
        )

        with pytest.raises(RuntimeError, match="事件流顺序不合法"):
            v19.run(conn)
    finally:
        conn.close()


def test_ensure_schema_rejects_current_version_with_stale_v18_event_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "stale_v18_event_contract.db"
    conn = get_connection(str(db_path))
    try:
        prepare_legacy_v17_execution_schema(conn, schedule_ids=(100,), operation_ids=(10,))
        v18.run(conn)
        conn.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO SchemaVersion(id, version) VALUES (1, 19);
            """
        )
        conn.commit()
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()

    with pytest.raises(MigrationContractError) as exc_info:
        ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))

    _assert_current_contract_error(exc_info.value, "bad_default: OperationExecutionEvents.source_table must not have default")


def test_ensure_schema_rejects_current_version_sparse_schema_shell(tmp_path: Path) -> None:
    db_path = tmp_path / "current_version_sparse_shell.db"
    _create_schema_version_shell(db_path, CURRENT_SCHEMA_VERSION)

    with pytest.raises(MigrationContractError) as exc_info:
        ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))

    _assert_current_contract_error(exc_info.value, "missing_table: OperationExecutionEvents")
    assert _user_table_count(db_path) == 0


def test_ensure_schema_rejects_version_15_missing_event_table(tmp_path: Path) -> None:
    db_path = tmp_path / "v15_missing_event_table.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO SchemaVersion(id, version) VALUES (1, 15);
            CREATE TABLE Schedule(id INTEGER PRIMARY KEY);
            """
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(MigrationContractError) as exc_info:
        ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))

    message = str(exc_info.value)
    assert "缺失整表：OperationExecutionEvents" in message, message
    conn = sqlite3.connect(str(db_path))
    try:
        version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0]
        assert int(version) == 15
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='OperationExecutionEvents'"
        ).fetchone() is None
    finally:
        conn.close()


def test_migration_runner_rejects_current_version_shell_before_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "current_version_runner_shell.db"
    _create_schema_version_shell(db_path, CURRENT_SCHEMA_VERSION)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with pytest.raises(MigrationContractError) as preflight_exc:
        migration_runner.preflight_migration_contract(
            str(db_path),
            to_version=CURRENT_SCHEMA_VERSION,
            schema_sql=schema_sql,
            connection_factory=get_connection,
        )
    _assert_current_contract_error(preflight_exc.value, "missing_table: OperationExecutionEvents")

    with pytest.raises(MigrationContractError) as apply_exc:
        migration_runner._apply_migrations(
            str(db_path),
            to_version=CURRENT_SCHEMA_VERSION,
            schema_sql=schema_sql,
            logger=None,
            connection_factory=get_connection,
        )
    _assert_current_contract_error(apply_exc.value, "missing_table: OperationExecutionEvents")
    assert _user_table_count(db_path) == 0
