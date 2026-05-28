from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_START,
)
from core.services.scheduler.operation_execution_labels import (
    event_type_to_action,
    execution_action_label,
    execution_status_label,
)
from data.repositories import OperationExecutionEventRepo, OperationExecutionEventRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _index_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    return {str(row["name"]) for row in rows}


def _index_columns(conn: sqlite3.Connection, name: str):
    rows = conn.execute(f"PRAGMA index_info({name})").fetchall()
    return [str(row["name"]) for row in rows]


def _foreign_targets(conn: sqlite3.Connection, table: str) -> Set[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    return {str(row["table"]) for row in rows}


def _seed_plan(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '一号设备', 'active'), ('M2', '二号设备', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '张三', 'active'), ('O2', '李四', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 1, 1, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def _event(**overrides):
    data = {
        "schedule_version": 1,
        "schedule_id": 100,
        "op_id": 10,
        "batch_id": "B1",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
        "event_type": EXECUTION_EVENT_START,
        "reported_status": "processing",
        "event_time": "2026-05-01 08:10:00",
        "actual_machine_id": "M1",
        "actual_operator_id": "O1",
        "created_by": "张三",
        "idempotency_key": "key-start",
        "request_fingerprint": "fingerprint-start",
        "previous_state_revision": "10:0:0",
    }
    data.update(overrides)
    return data


def test_operation_execution_schema_contract_in_fresh_database(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert "OperationExecutionEvents" in _table_names(conn)
        assert {
            "idx_operation_execution_events_op",
            "idx_operation_execution_events_schedule",
            "idx_operation_execution_events_schedule_op",
            "idx_operation_execution_events_batch",
            "idx_operation_execution_events_op_revision_unique",
            "idx_operation_execution_events_latest_exception",
        } <= _index_names(conn)
        assert _index_columns(conn, "idx_operation_execution_events_op") == ["op_id", "event_time"]
        assert _index_columns(conn, "idx_operation_execution_events_op_revision_unique") == [
            "op_id",
            "previous_state_revision",
        ]
        assert {"Schedule", "BatchOperations"} <= _foreign_targets(conn, "OperationExecutionEvents")
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def test_operation_execution_repository_appends_and_aggregates_state(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        start = repo.insert_event(_event())
        exception = repo.insert_event(
            _event(
                event_type=EXECUTION_EVENT_EXCEPTION,
                reported_status="exception",
                event_time="2026-05-01 08:30:00",
                reason_code="equipment",
                severity="high",
                impact_minutes=30,
                affected_machine_id="M2",
                affected_operator_id="O2",
                handling_status="new",
                suggest_reschedule="yes",
                remark="设备突然停了",
                idempotency_key="key-exception",
                request_fingerprint="fingerprint-exception",
                previous_state_revision=f"10:1:{start.id}",
            )
        )
        finish = repo.insert_event(
            _event(
                event_type=EXECUTION_EVENT_FINISH,
                reported_status="completed",
                event_time="2026-05-01 09:20:00",
                quantity_done=10,
                remark="已做完",
                idempotency_key="key-finish",
                request_fingerprint="fingerprint-finish",
                previous_state_revision=f"10:2:{exception.id}",
            )
        )
        conn.commit()

        assert repo.get_event_by_id(int(start.id or 0)).id == start.id
        assert repo.get_by_idempotency_key("key-exception").id == exception.id
        assert repo.list_latest_events_by_op_ids([10])[10].id == finish.id
        assert repo.list_latest_exception_events_by_op_ids([10])[10].id == exception.id

        state = repo.aggregate_states_by_op_ids([10])[10]
        assert state.current_status == "completed"
        assert state.current_status_label == "已完工"
        assert state.last_event_id == finish.id
        assert state.last_event_action_label == "完工"
        assert state.latest_exception_event_id == exception.id
        assert state.latest_exception_reason_label == "设备问题"
        assert state.latest_exception_severity_label == "严重"
        assert state.latest_exception_impact_minutes_label == "预计影响 30 分钟"
        assert state.latest_exception_affected_machine_label == "M2 二号设备"
        assert state.latest_exception_affected_machine_display_label == "二号设备"
        assert state.latest_exception_affected_machine_identity_label == "M2 二号设备"
        assert state.latest_exception_affected_operator_label == "O2 李四"
        assert state.latest_exception_affected_operator_display_label == "李四"
        assert state.latest_exception_affected_operator_identity_label == "O2 李四"
        assert state.latest_exception_suggest_reschedule_label == "建议重新排程"
        assert state.state_revision == f"10:3:{finish.id}"
    finally:
        conn.close()


def test_operation_execution_state_keeps_fractional_minutes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        start = repo.insert_event(
            _event(
                event_time="2026-05-01 08:00:30",
            )
        )
        paused = repo.insert_event(
            _event(
                event_type="pause",
                reported_status="paused",
                event_time="2026-05-01 08:01:00",
                reason_code="equipment",
                idempotency_key="key-pause-fractional",
                request_fingerprint="fingerprint-pause-fractional",
                previous_state_revision=f"10:1:{start.id}",
            )
        )
        resumed = repo.insert_event(
            _event(
                event_type="resume",
                reported_status="processing",
                event_time="2026-05-01 08:01:30",
                idempotency_key="key-resume-fractional",
                request_fingerprint="fingerprint-resume-fractional",
                previous_state_revision=f"10:2:{paused.id}",
            )
        )
        finish = repo.insert_event(
            _event(
                event_type=EXECUTION_EVENT_FINISH,
                reported_status="completed",
                event_time="2026-05-01 08:02:00",
                quantity_done=10,
                idempotency_key="key-finish-fractional",
                request_fingerprint="fingerprint-finish-fractional",
                previous_state_revision=f"10:3:{resumed.id}",
            )
        )
        conn.commit()

        state = repo.aggregate_states_by_op_ids([10])[10]
        assert state.last_event_id == finish.id
        assert state.actual_duration_minutes == 1.5
        assert state.pause_duration_minutes == 0.5
    finally:
        conn.close()


def test_operation_execution_repository_alias_is_exported() -> None:
    assert OperationExecutionEventRepository is OperationExecutionEventRepo


def test_operation_execution_labels_keep_status_and_action_plain_chinese() -> None:
    assert execution_status_label("exception") == "异常中"
    assert event_type_to_action("exception") == EXECUTION_ACTION_REPORT_EXCEPTION
    assert execution_action_label(EXECUTION_ACTION_REPORT_EXCEPTION) == "报异常"
    assert execution_action_label("exception") == "报异常"


def test_operation_execution_database_rejects_bad_values_and_duplicates(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        repo.insert_event(_event())
        conn.commit()

        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-bad", event_type="running"))
        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-bad-status", reported_status="finished"))
        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-bad-source", source_table="candidate_rows"))
        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-negative", quantity_done=-1))
        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-start", previous_state_revision="10:1:1"))
        with pytest.raises(Exception):
            repo.insert_event(_event(idempotency_key="key-other", previous_state_revision="10:0:0"))
    finally:
        conn.close()
