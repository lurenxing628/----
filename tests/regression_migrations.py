from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v15 import _EVENT_INDEX_SQL, _EVENT_TABLE_SQL

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


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


def test_fresh_schema_and_repeated_ensure_schema_are_current(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh_twice.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
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
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion (id, version) VALUES (1, 14);
            DROP INDEX IF EXISTS idx_operation_execution_events_latest_exception;
            DROP INDEX IF EXISTS idx_operation_execution_events_op_revision_unique;
            DROP INDEX IF EXISTS idx_operation_execution_events_batch;
            DROP INDEX IF EXISTS idx_operation_execution_events_schedule_op;
            DROP INDEX IF EXISTS idx_operation_execution_events_schedule;
            DROP INDEX IF EXISTS idx_operation_execution_events_op;
            DROP TABLE OperationExecutionEvents;
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            """
        )
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


def test_v15_database_repairs_early_operation_execution_event_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v15.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _replace_operation_execution_events_with_legacy_v15(conn)
        _seed_minimal_plan(conn)
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, reason_code, severity,
                suggest_reschedule, created_by, idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                    '2026-05-01 08:10:00', 'equipment', 'high', 'yes', '张三',
                    'legacy-v15-key', 'legacy-fingerprint', '10:0:0')
            """
        )
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, reason_code,
                suggest_reschedule, created_by, idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'pause', 'paused',
                    '2026-05-01 08:15:00', NULL, 'no', '张三',
                    'legacy-v15-missing-pause-reason', 'legacy-fingerprint-2', '10:1:1')
            """
        )
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, reason_code, severity,
                actual_machine_id, actual_operator_id, affected_machine_id, affected_operator_id, suggest_reschedule, remark,
                created_by, idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                    '2026-05-01 08:20:00', 'equipment', NULL,
                    '', '', 'M-missing', 'O-missing', 'yes', '旧异常备注', '张三',
                    'legacy-v15-missing-severity', 'legacy-fingerprint-3', '10:2:2')
            """
        )
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, reason_code, severity,
                actual_machine_id, actual_operator_id, affected_machine_id, affected_operator_id, suggest_reschedule,
                created_by, idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                    '2026-05-01 08:25:00', 'equipment', NULL,
                    'M1', 'O1', 'M1', 'O1', 'yes', '张三',
                    'legacy-v15-missing-severity-only', 'legacy-fingerprint-4', '10:3:3')
            """
        )
        conn.execute("DELETE FROM SchemaVersion")
        conn.execute("INSERT INTO SchemaVersion (id, version) VALUES (1, 15)")
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_v15_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        row = conn.execute(
            "SELECT suggest_reschedule FROM OperationExecutionEvents WHERE idempotency_key = ?",
            ("legacy-v15-key",),
        ).fetchone()
        assert int(row["suggest_reschedule"]) == 1
        pause_row = conn.execute(
            """
            SELECT reason_code, reason_detail
            FROM OperationExecutionEvents
            WHERE idempotency_key = ?
            """,
            ("legacy-v15-missing-pause-reason",),
        ).fetchone()
        assert pause_row["reason_code"] == "other"
        assert "迁移补齐" in pause_row["reason_detail"]
        exception_row = conn.execute(
            """
            SELECT severity, actual_machine_id, actual_operator_id, affected_machine_id, affected_operator_id, remark
            FROM OperationExecutionEvents
            WHERE idempotency_key = ?
            """,
            ("legacy-v15-missing-severity",),
        ).fetchone()
        assert exception_row["severity"] == "medium"
        assert exception_row["actual_machine_id"] is None
        assert exception_row["actual_operator_id"] is None
        assert exception_row["affected_machine_id"] is None
        assert exception_row["affected_operator_id"] is None
        assert "迁移补齐" in exception_row["remark"]
        severity_only_row = conn.execute(
            """
            SELECT severity, reason_detail, remark
            FROM OperationExecutionEvents
            WHERE idempotency_key = ?
            """,
            ("legacy-v15-missing-severity-only",),
        ).fetchone()
        assert severity_only_row["severity"] == "medium"
        assert "严重程度" in severity_only_row["reason_detail"]
        assert severity_only_row["remark"] is None
        assert detect_schema_is_current(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, reason_code, severity,
                    suggest_reschedule, created_by, idempotency_key, request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                        '2026-05-01 08:20:00', 'equipment', 'high', 2, '张三',
                        'bad-suggest-after-v16', 'fingerprint-bad-suggest', '10:1:1')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'pause', 'paused',
                        '2026-05-01 08:25:00', '张三',
                        'missing-pause-reason-after-v16', 'fingerprint-missing-reason', '10:1:2')
                """
            )
    finally:
        conn.close()


def test_detect_schema_requires_execution_unique_index_and_column_order(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP INDEX idx_operation_execution_events_op")
        conn.execute("CREATE INDEX idx_operation_execution_events_op ON OperationExecutionEvents(event_time, op_id)")
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_execution_indexes_on_another_table(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.executescript(
            """
            DROP INDEX idx_operation_execution_events_latest_exception;
            DROP INDEX idx_operation_execution_events_op_revision_unique;
            DROP INDEX idx_operation_execution_events_batch;
            DROP INDEX idx_operation_execution_events_schedule_op;
            DROP INDEX idx_operation_execution_events_schedule;
            DROP INDEX idx_operation_execution_events_op;

            CREATE TABLE OperationExecutionEventsIndexShadow (
                id INTEGER,
                op_id INTEGER,
                event_time DATETIME,
                schedule_id INTEGER,
                batch_id TEXT,
                event_type TEXT,
                previous_state_revision TEXT
            );
            CREATE INDEX idx_operation_execution_events_op
            ON OperationExecutionEventsIndexShadow(op_id, event_time);
            CREATE INDEX idx_operation_execution_events_schedule
            ON OperationExecutionEventsIndexShadow(schedule_id);
            CREATE INDEX idx_operation_execution_events_schedule_op
            ON OperationExecutionEventsIndexShadow(schedule_id, op_id);
            CREATE INDEX idx_operation_execution_events_batch
            ON OperationExecutionEventsIndexShadow(batch_id);
            CREATE UNIQUE INDEX idx_operation_execution_events_op_revision_unique
            ON OperationExecutionEventsIndexShadow(op_id, previous_state_revision);
            CREATE INDEX idx_operation_execution_events_latest_exception
            ON OperationExecutionEventsIndexShadow(op_id, event_type, id);
            """
        )
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_operation_execution_id_without_primary_key(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(_EVENT_TABLE_SQL.replace("id                       INTEGER PRIMARY KEY AUTOINCREMENT", "id                       INTEGER"))
        for sql in _EVENT_INDEX_SQL:
            conn.execute(sql)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_operation_execution_cascade_parent_foreign_keys(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(
            _EVENT_TABLE_SQL.replace(
                "FOREIGN KEY (schedule_id) REFERENCES Schedule(id)",
                "FOREIGN KEY (schedule_id) REFERENCES Schedule(id) ON DELETE CASCADE",
            ).replace(
                "FOREIGN KEY (op_id) REFERENCES BatchOperations(id)",
                "FOREIGN KEY (op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE",
            )
        )
        for sql in _EVENT_INDEX_SQL:
            conn.execute(sql)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_operation_execution_wrong_foreign_key_mapping(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(
            """
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
                FOREIGN KEY (op_id) REFERENCES Schedule(id) ON DELETE CASCADE,
                FOREIGN KEY (schedule_version) REFERENCES BatchOperations(id) ON DELETE CASCADE,
                UNIQUE(op_id, previous_state_revision),
                CHECK(schedule_version > 0),
                CHECK(schedule_id > 0),
                CHECK(op_id > 0),
                CHECK(TRIM(batch_id) <> ''),
                CHECK(TRIM(created_by) <> ''),
                CHECK(TRIM(idempotency_key) <> ''),
                CHECK(TRIM(request_fingerprint) <> ''),
                CHECK(TRIM(previous_state_revision) <> '')
            )
            """
        )
        _create_operation_execution_indexes(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_missing_operation_execution_resource_foreign_keys(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(
            """
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
                CHECK(quantity_done IS NULL OR quantity_done >= 0),
                CHECK(quantity_scrapped IS NULL OR quantity_scrapped >= 0),
                CHECK(impact_minutes IS NULL OR impact_minutes >= 0),
                CHECK(TRIM(batch_id) <> ''),
                CHECK(TRIM(created_by) <> ''),
                CHECK(TRIM(idempotency_key) <> ''),
                CHECK(TRIM(request_fingerprint) <> ''),
                CHECK(TRIM(previous_state_revision) <> '')
            )
            """
        )
        _create_operation_execution_indexes(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_operation_execution_widened_check(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(
            """
            CREATE TABLE OperationExecutionEvents (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_version         INTEGER NOT NULL,
                schedule_id              INTEGER NOT NULL,
                op_id                    INTEGER NOT NULL,
                batch_id                 TEXT NOT NULL,
                source_table             TEXT NOT NULL DEFAULT 'schedule' CHECK(source_table = 'schedule'),
                effective_plan_role      TEXT NOT NULL DEFAULT 'adopted' CHECK(effective_plan_role = 'adopted'),
                scenario_id              TEXT CHECK(scenario_id IS NULL),
                event_type               TEXT NOT NULL CHECK(event_type IN ('start', 'pause', 'resume', 'finish', 'exception') OR event_type = 'running'),
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
            )
            """
        )
        _create_operation_execution_indexes(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def _create_operation_execution_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_operation_execution_events_op
        ON OperationExecutionEvents(op_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule
        ON OperationExecutionEvents(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule_op
        ON OperationExecutionEvents(schedule_id, op_id);
        CREATE INDEX IF NOT EXISTS idx_operation_execution_events_batch
        ON OperationExecutionEvents(batch_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_execution_events_op_revision_unique
        ON OperationExecutionEvents(op_id, previous_state_revision);
        CREATE INDEX IF NOT EXISTS idx_operation_execution_events_latest_exception
        ON OperationExecutionEvents(op_id, event_type, id);
        """
    )


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
    _create_operation_execution_indexes(conn)


def test_operation_execution_constraints_reject_invalid_rows(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        _seed_minimal_plan(conn)
        params = (
            1,
            100,
            10,
            "B1",
            "schedule",
            "adopted",
            None,
            "start",
            "processing",
            "2026-05-01 08:10:00",
            "张三",
            "key-1",
            "fingerprint",
            "10:0:0",
        )
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                request_fingerprint, previous_state_revision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'start', 'processing',
                        '2026-05-01 08:11:00', '张三', 'key-1', 'fingerprint-2', '10:1:1')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B1', 'candidate_rows', 'adopted', NULL, 'start', 'processing',
                        '2026-05-01 08:12:00', '张三', 'key-2', 'fingerprint-2', '10:1:1')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision, impact_minutes
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                        '2026-05-01 08:12:00', '张三', 'key-3', 'fingerprint-3', '10:1:1', -1)
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'pause', 'paused',
                        '2026-05-01 08:13:00', '张三', 'key-4', 'fingerprint-4', '10:1:2')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision, reason_code
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                        '2026-05-01 08:14:00', '张三', 'key-5', 'fingerprint-5', '10:1:3', 'equipment')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO OperationExecutionEvents(
                    schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                    scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                    request_fingerprint, previous_state_revision, reason_code, severity, suggest_reschedule
                )
                VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'exception', 'exception',
                        '2026-05-01 08:15:00', '张三', 'key-6', 'fingerprint-6', '10:1:4', 'equipment', 'high', 2)
                """
            )
    finally:
        conn.close()


def test_operation_execution_events_block_parent_delete(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        _seed_minimal_plan(conn)
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                request_fingerprint, previous_state_revision
            )
            VALUES (1, 100, 10, 'B1', 'schedule', 'adopted', NULL, 'start', 'processing',
                    '2026-05-01 08:10:00', '张三', 'delete-parent-key', 'fingerprint', '10:0:0')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM Schedule WHERE id = 100")
        row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents").fetchone()
        assert int(row["count"]) == 1
    finally:
        conn.close()
