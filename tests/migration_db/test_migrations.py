"""新库初始化幂等，旧库迁移保留业务数据。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v15 import _EVENT_INDEX_SQL
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
# Frozen from 244fbb7e5cfe68713e59b15a741d8e459657b207:schema.sql.
LEGACY_V14_SCHEMA_PATH = Path(__file__).parent / "fixtures" / "schema-v14.sql"


def _table_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _connect_fresh(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "fresh.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _seed_minimal_plan(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name)
        VALUES ('M1', '一号设备');

        INSERT INTO Operators(operator_id, name)
        VALUES ('O1', '张三');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 1);
        """
    )


def test_fresh_schema_and_repeated_ensure_schema_are_current(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fresh_twice.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    from core.infrastructure import database
    checked_transactions = []
    check = database._ensure_current_schema_contract
    def counted_check(conn, **kwargs):
        checked_transactions.append(conn.in_transaction)
        return check(conn, **kwargs)
    monkeypatch.setattr(database, "_ensure_current_schema_contract", counted_check)
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    assert checked_transactions == [True]
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert "OperationExecutionEvents" in _table_names(conn)
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def test_v14_database_migrates_operation_execution_events_without_losing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v14.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(LEGACY_V14_SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion (id, version) VALUES (1, 14);
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            """
        )
        assert "OperationExecutionEvents" not in _table_names(conn)
        assert not any(name.startswith("Workbench") for name in _table_names(conn))
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert "OperationExecutionEvents" in _table_names(conn)
        assert conn.execute("SELECT name FROM LegacyRows WHERE id = 1").fetchone()["name"] == "keep-me"
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def _replace_operation_execution_events_with_legacy_v15(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP INDEX IF EXISTS idx_operation_execution_events_latest_exception;
        DROP INDEX IF EXISTS idx_operation_execution_events_op_revision_unique;
        DROP INDEX IF EXISTS idx_operation_execution_events_batch;
        DROP INDEX IF EXISTS idx_operation_execution_events_schedule_op;
        DROP INDEX IF EXISTS idx_operation_execution_events_schedule;
        DROP INDEX IF EXISTS idx_operation_execution_events_op;
        DROP TABLE IF EXISTS OperationExecutionEvents;
        CREATE TABLE OperationExecutionEvents (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_version         INTEGER NOT NULL,
            schedule_id              INTEGER NOT NULL,
            op_id                    INTEGER NOT NULL,
            batch_id                 TEXT NOT NULL,
            source_table             TEXT NOT NULL DEFAULT 'schedule' CHECK(source_table = 'schedule'),
            effective_plan_role      TEXT NOT NULL DEFAULT 'adopted' CHECK(effective_plan_role = 'adopted'),
            scenario_id              TEXT CHECK(scenario_id IS NULL),
            event_type               TEXT NOT NULL CHECK(event_type IN ('start', 'pause', 'resume', 'finish', 'exception')),
            reported_status          TEXT NOT NULL CHECK(reported_status IN ('processing', 'paused', 'exception', 'completed')),
            event_time               DATETIME NOT NULL,
            actual_machine_id        TEXT,
            actual_operator_id       TEXT,
            quantity_done            INTEGER CHECK(quantity_done IS NULL OR quantity_done >= 0),
            quantity_scrapped        INTEGER CHECK(quantity_scrapped IS NULL OR quantity_scrapped >= 0),
            reason_code              TEXT CHECK(reason_code IS NULL OR reason_code IN ('equipment', 'person', 'material', 'quality', 'process', 'external', 'other')),
            reason_detail            TEXT,
            severity                 TEXT CHECK(severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')),
            impact_minutes           INTEGER CHECK(impact_minutes IS NULL OR impact_minutes >= 0),
            affected_machine_id      TEXT,
            affected_operator_id     TEXT,
            handling_status          TEXT CHECK(handling_status IS NULL OR handling_status IN ('new', 'checking', 'waiting', 'handled')),
            suggest_reschedule       TEXT CHECK(suggest_reschedule IS NULL OR suggest_reschedule IN ('yes', 'no')),
            remark                   TEXT,
            created_by               TEXT NOT NULL,
            idempotency_key          TEXT NOT NULL UNIQUE,
            request_fingerprint      TEXT NOT NULL,
            previous_state_revision  TEXT NOT NULL,
            created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (schedule_id) REFERENCES Schedule(id) ON DELETE CASCADE,
            FOREIGN KEY (op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE,
            UNIQUE(op_id, previous_state_revision),
            CHECK(schedule_version > 0),
            CHECK(schedule_id > 0),
            CHECK(op_id > 0),
            CHECK(TRIM(batch_id) <> ''),
            CHECK(TRIM(created_by) <> ''),
            CHECK(TRIM(idempotency_key) <> ''),
            CHECK(TRIM(request_fingerprint) <> ''),
            CHECK(TRIM(previous_state_revision) <> '')
        );
        """
    )
    for sql in _EVENT_INDEX_SQL:
        conn.execute(sql)
