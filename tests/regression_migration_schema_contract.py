"""回归测试：detect_schema_is_current 与 operation_execution_event_contract_issues 守护 OperationExecutionEvents 表契约——唯一索引/列顺序、索引须建在本表而非影子表、id 主键、event_time CHECK、外键须为复合组（schedule(id,version,op_id) 与 BatchOperations(id,batch_id)）不可拆分/不可改 CASCADE/不可错配资源外键、CHECK 不可放宽枚举，以及已存在脏数据（不可能日期、状态对不上、各字段越界）都应被判定为 schema 不当前。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.migration_operation_execution_contract import operation_execution_event_contract_issues
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v15 import _EVENT_INDEX_SQL, _EVENT_TABLE_SQL
from tests._support.paths import REPO_ROOT
from tests.operation_execution_feedback_test_support import _seed_execution_feedback_context

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect_fresh(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "fresh.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _create_operation_execution_indexes(conn: sqlite3.Connection) -> None:
    for sql in _EVENT_INDEX_SQL:
        conn.execute(sql)


def _insert_existing_execution_event_with_ignored_checks(conn: sqlite3.Connection, **overrides) -> None:
    payload = {
        "schedule_version": 2,
        "schedule_id": 100,
        "op_id": 10,
        "batch_id": "B1",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
        "event_type": "start",
        "reported_status": "processing",
        "event_time": "2026-05-01 08:10:00",
        "created_by": "pytest",
        "idempotency_key": "bad-existing-event",
        "request_fingerprint": "bad-existing-event-fingerprint",
        "previous_state_revision": "10:0:0",
        "reason_code": None,
        "severity": None,
        "impact_minutes": None,
        "handling_status": None,
        "suggest_reschedule": 0,
    }
    payload.update(overrides)
    columns = ", ".join(payload)
    placeholders = ", ".join("?" for _ in payload)
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA ignore_check_constraints = ON")
    try:
        conn.execute(
            f"INSERT INTO OperationExecutionEvents ({columns}) VALUES ({placeholders})",
            tuple(payload.values()),
        )
    finally:
        conn.execute("PRAGMA ignore_check_constraints = OFF")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")


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
        _create_operation_execution_indexes(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_operation_execution_without_event_time_check(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(
            _EVENT_TABLE_SQL.replace("    CHECK(TRIM(event_time) <> '' AND datetime(event_time) IS NOT NULL),\n", "")
        )
        _create_operation_execution_indexes(conn)

        issues = operation_execution_event_contract_issues(conn)
        assert any("event_time" in issue for issue in issues), issues
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_existing_operation_execution_impossible_event_time(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        _seed_execution_feedback_context(conn)
        _insert_existing_execution_event_with_ignored_checks(
            conn,
            event_time="2026-02-30 08:10:00",
        )

        issues = operation_execution_event_contract_issues(conn)
        assert any("bad_data: OperationExecutionEvents.id=" in issue and "event_time" in issue for issue in issues)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_existing_operation_execution_bad_status_pair(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        _seed_execution_feedback_context(conn)
        _insert_existing_execution_event_with_ignored_checks(
            conn,
            reported_status="completed",
        )

        issues = operation_execution_event_contract_issues(conn)
        assert any("bad_data: OperationExecutionEvents.id=" in issue and "does not match" in issue for issue in issues)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("overrides", "expected_issue"),
    [
        ({"source_table": "candidate_rows"}, "source_table"),
        ({"effective_plan_role": "baseline_best"}, "effective_plan_role"),
        ({"scenario_id": "scenario-1"}, "scenario_id"),
        ({"schedule_version": 0}, "schedule_version"),
        ({"schedule_id": 0}, "schedule_id"),
        ({"op_id": 0}, "op_id"),
        ({"batch_id": ""}, "batch_id"),
        ({"quantity_done": -1}, "quantity_done"),
        ({"quantity_scrapped": -1}, "quantity_scrapped"),
        ({"impact_minutes": -1}, "impact_minutes"),
        ({"event_type": "pause", "reported_status": "paused", "reason_code": None}, "reason_code"),
        (
            {"event_type": "exception", "reported_status": "exception", "reason_code": "equipment", "severity": None},
            "severity",
        ),
        ({"suggest_reschedule": 2}, "suggest_reschedule"),
        ({"created_by": ""}, "created_by"),
        ({"idempotency_key": ""}, "idempotency_key"),
        ({"request_fingerprint": ""}, "request_fingerprint"),
        ({"previous_state_revision": ""}, "previous_state_revision"),
    ],
)
def test_detect_schema_rejects_existing_operation_execution_bad_contract_values(
    tmp_path: Path, overrides, expected_issue: str
) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        _seed_execution_feedback_context(conn)
        _insert_existing_execution_event_with_ignored_checks(conn, **overrides)

        issues = operation_execution_event_contract_issues(conn)
        assert any("bad_data: OperationExecutionEvents.id=" in issue and expected_issue in issue for issue in issues)
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
                "FOREIGN KEY (schedule_id, schedule_version, op_id) REFERENCES Schedule(id, version, op_id)",
                "FOREIGN KEY (schedule_id, schedule_version, op_id) REFERENCES Schedule(id, version, op_id) ON DELETE CASCADE",
            ).replace(
                "FOREIGN KEY (op_id, batch_id) REFERENCES BatchOperations(id, batch_id)",
                "FOREIGN KEY (op_id, batch_id) REFERENCES BatchOperations(id, batch_id) ON DELETE CASCADE",
            )
        )
        _create_operation_execution_indexes(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_detect_schema_rejects_split_operation_execution_foreign_key_groups(tmp_path: Path) -> None:
    conn = _connect_fresh(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE OperationExecutionEvents")
        split_fk_sql = _EVENT_TABLE_SQL.replace(
            "FOREIGN KEY (schedule_id, schedule_version, op_id) REFERENCES Schedule(id, version, op_id)",
            "\n".join(
                [
                    "FOREIGN KEY (schedule_id) REFERENCES Schedule(id),",
                    "FOREIGN KEY (schedule_version) REFERENCES Schedule(version),",
                    "FOREIGN KEY (op_id) REFERENCES Schedule(op_id)",
                ]
            ),
        ).replace(
            "FOREIGN KEY (op_id, batch_id) REFERENCES BatchOperations(id, batch_id)",
            "\n".join(
                [
                    "FOREIGN KEY (op_id) REFERENCES BatchOperations(id),",
                    "FOREIGN KEY (batch_id) REFERENCES BatchOperations(batch_id)",
                ]
            ),
        )
        conn.execute(split_fk_sql)
        _create_operation_execution_indexes(conn)

        issues = operation_execution_event_contract_issues(conn)
        assert any("bad_fk_group" in issue for issue in issues), issues
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
