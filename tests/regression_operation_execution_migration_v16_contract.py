from __future__ import annotations

import sqlite3

import pytest

from core.infrastructure.migrations import v16


def _connect_malformed_legacy_events() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE Schedule(id INTEGER PRIMARY KEY, version INTEGER NOT NULL, op_id INTEGER NOT NULL);
        CREATE TABLE BatchOperations(id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL);
        CREATE TABLE Machines(machine_id TEXT PRIMARY KEY);
        CREATE TABLE Operators(operator_id TEXT PRIMARY KEY);
        CREATE UNIQUE INDEX idx_schedule_identity_unique ON Schedule(id, version, op_id);
        CREATE UNIQUE INDEX idx_batch_operations_identity_unique ON BatchOperations(id, batch_id);
        INSERT INTO Schedule(id, version, op_id) VALUES (100, 1, 10);
        INSERT INTO BatchOperations(id, batch_id) VALUES (10, 'B1');

        CREATE TABLE OperationExecutionEvents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_version INTEGER,
            schedule_id INTEGER,
            op_id INTEGER,
            batch_id TEXT,
            source_table TEXT,
            effective_plan_role TEXT,
            scenario_id TEXT,
            event_type TEXT,
            reported_status TEXT,
            event_time DATETIME,
            actual_machine_id TEXT,
            actual_operator_id TEXT,
            quantity_done INTEGER,
            quantity_scrapped INTEGER,
            reason_code TEXT,
            reason_detail TEXT,
            severity TEXT,
            impact_minutes INTEGER,
            affected_machine_id TEXT,
            affected_operator_id TEXT,
            handling_status TEXT,
            suggest_reschedule INTEGER,
            remark TEXT,
            created_by TEXT,
            idempotency_key TEXT,
            request_fingerprint TEXT,
            previous_state_revision TEXT,
            created_at DATETIME
        );
        """
    )
    return conn


def _insert_legacy_event(conn: sqlite3.Connection, **overrides) -> None:
    payload = {
        "schedule_version": 1,
        "schedule_id": 100,
        "op_id": 10,
        "batch_id": "B1",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
        "event_type": "exception",
        "reported_status": "exception",
        "event_time": "2026-05-01 08:00:00",
        "actual_machine_id": None,
        "actual_operator_id": None,
        "quantity_done": None,
        "quantity_scrapped": None,
        "reason_code": "equipment",
        "reason_detail": None,
        "severity": "high",
        "impact_minutes": None,
        "affected_machine_id": None,
        "affected_operator_id": None,
        "handling_status": None,
        "suggest_reschedule": 0,
        "remark": None,
        "created_by": "pytest",
        "idempotency_key": "legacy-key",
        "request_fingerprint": "legacy-fingerprint",
        "previous_state_revision": "10:0:legacy",
        "created_at": "2026-05-01 08:01:00",
    }
    payload.update(overrides)
    columns = ", ".join(payload)
    placeholders = ", ".join("?" for _ in payload)
    conn.execute(
        f"INSERT INTO OperationExecutionEvents ({columns}) VALUES ({placeholders})",
        tuple(payload.values()),
    )


def test_v16_rejects_legacy_pause_or_exception_without_reason() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, event_type="pause", reported_status="paused", reason_code=None)

        with pytest.raises(RuntimeError, match="缺少暂停/异常原因"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_exception_without_severity() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, reason_code="equipment", severity=None)

        with pytest.raises(RuntimeError, match="缺少异常严重程度"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_missing_resource_reference() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(
            conn,
            event_type="start",
            reported_status="processing",
            actual_machine_id="M-MISSING",
        )

        with pytest.raises(RuntimeError, match="引用了不存在设备或人员"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_invalid_suggest_reschedule() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, suggest_reschedule="maybe")

        with pytest.raises(RuntimeError, match="重排建议不是"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_missing_suggest_reschedule() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, suggest_reschedule=None)

        with pytest.raises(RuntimeError, match="缺少重排建议"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_blank_suggest_reschedule() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, suggest_reschedule=" ")

        with pytest.raises(RuntimeError, match="缺少重排建议"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_without_created_at() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, created_at=None)

        with pytest.raises(RuntimeError, match="缺少创建时间"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_bad_event_time() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, event_time="not-a-date")

        with pytest.raises(RuntimeError, match="事件时间缺失或格式不正确"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_blank_created_at() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, created_at=" ")

        with pytest.raises(RuntimeError, match="缺少创建时间"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_with_bad_status_pair() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(conn, event_type="finish", reported_status="processing")

        with pytest.raises(RuntimeError, match="事件类型和上报状态互相矛盾"):
            v16.run(conn)
    finally:
        conn.close()


def test_v16_rejects_legacy_event_sequence_without_start() -> None:
    conn = _connect_malformed_legacy_events()
    try:
        _insert_legacy_event(
            conn,
            event_type="finish",
            reported_status="completed",
            quantity_done=10,
        )

        with pytest.raises(RuntimeError, match="事件流顺序不合法"):
            v16.run(conn)
    finally:
        conn.close()
