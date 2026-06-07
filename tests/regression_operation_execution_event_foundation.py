"""回归测试：OperationExecutionEvents 表/索引/外键的 schema 契约与 OperationExecutionEventRepo 的写入读取——DB 层 CHECK/触发器拒绝身份不一致与事件-状态对不匹配；仓库要求显式完整计划身份（source_table/effective_plan_role），拒绝越权 op_id 读取，按 idempotency_key/scope 回读并聚合出完工/异常状态及中文标签（已完工、报异常、设备问题等）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.operation_execution_event_data_contract import operation_execution_event_sequence_issues
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_START,
    OperationExecutionEvent,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import OperationExecutionScope
from core.services.scheduler.operation_execution_labels import (
    event_type_to_action,
    execution_action_label,
    execution_status_label,
)
from data.repositories import OperationExecutionEventRepo, OperationExecutionEventRepository
from tests._support.paths import REPO_ROOT

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


def _seed_second_schedule(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ScheduleVersionSeq(version) VALUES (2);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (101, 10, 'M2', 'O2', '2026-05-02 08:00:00', '2026-05-02 09:00:00', 'unlocked', 2);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (2, 'priority_first', 1, 1, 'success', '{}', 'pytest');
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


def _insert_raw_event(conn: sqlite3.Connection, **overrides) -> None:
    payload = _event(**overrides)
    columns = ", ".join(payload)
    placeholders = ", ".join("?" for _ in payload)
    conn.execute(f"INSERT INTO OperationExecutionEvents ({columns}) VALUES ({placeholders})", tuple(payload.values()))


def _scope(schedule_version: int, schedule_id: int) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=schedule_version,
        schedule_id=schedule_id,
        op_id=10,
        batch_id="B1",
        source_table="schedule",
        effective_plan_role="adopted",
    )


def _assert_repository_readbacks(repo: OperationExecutionEventRepo, start, exception, finish) -> None:
    assert repo.get_event_by_id(int(start.id or 0)).id == start.id
    assert repo.get_by_idempotency_key("key-exception").id == exception.id
    events = repo.list_events_by_scope(_scope(1, 100))
    exception_events = [event for event in events if event.event_type == EXECUTION_EVENT_EXCEPTION]
    assert events[-1].id == finish.id
    assert exception_events[-1].id == exception.id


def _assert_completed_execution_state(state, finish, exception) -> None:
    _assert_completed_state_header(state, finish, exception)
    _assert_exception_labels(state)
    _assert_exception_resource_labels(state)
    assert state.latest_exception_suggest_reschedule_label == "建议重新排程"
    assert state.state_revision == f"10:3:{finish.id}"


def _assert_completed_state_header(state, finish, exception) -> None:
    assert state.current_status == "completed"
    assert state.current_status_label == "已完工"
    assert state.last_event_id == finish.id
    assert state.last_event_action_label == "完工"
    assert state.latest_exception_event_id == exception.id


def _assert_exception_labels(state) -> None:
    assert state.latest_exception_reason_label == "设备问题"
    assert state.latest_exception_severity_label == "严重"
    assert state.latest_exception_impact_minutes_label == "预计影响 30 分钟"


def _assert_exception_resource_labels(state) -> None:
    assert state.latest_exception_affected_machine_label == "M2 二号设备"
    assert state.latest_exception_affected_machine_display_label == "二号设备"
    assert state.latest_exception_affected_machine_identity_label == "M2 二号设备"
    assert state.latest_exception_affected_operator_label == "O2 李四"
    assert state.latest_exception_affected_operator_display_label == "李四"
    assert state.latest_exception_affected_operator_identity_label == "O2 李四"


def test_operation_execution_schema_contract_in_fresh_database(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert "OperationExecutionEvents" in _table_names(conn)
        assert {
            "idx_schedule_identity_unique",
            "idx_batch_operations_identity_unique",
            "idx_operation_execution_events_op",
            "idx_operation_execution_events_schedule",
            "idx_operation_execution_events_schedule_op",
            "idx_operation_execution_events_batch",
            "idx_operation_execution_events_op_revision_unique",
            "idx_operation_execution_events_latest_exception",
        } <= _index_names(conn)
        assert _index_columns(conn, "idx_operation_execution_events_op") == ["op_id", "event_time"]
        assert _index_columns(conn, "idx_operation_execution_events_op_revision_unique") == [
            "schedule_version",
            "schedule_id",
            "op_id",
            "batch_id",
            "source_table",
            "effective_plan_role",
            "previous_state_revision",
        ]
        assert {"Schedule", "BatchOperations"} <= _foreign_targets(conn, "OperationExecutionEvents")
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def test_operation_execution_schema_rejects_direct_identity_mismatch(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_raw_event(conn, schedule_version=2, idempotency_key="bad-version", previous_state_revision="10:0:bad-version")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_raw_event(conn, batch_id="B2", idempotency_key="bad-batch", previous_state_revision="10:0:bad-batch")
    finally:
        conn.close()


def test_operation_execution_schema_rejects_event_status_pair_mismatch(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_raw_event(
                conn,
                event_type=EXECUTION_EVENT_FINISH,
                reported_status="processing",
                idempotency_key="bad-status-pair",
                previous_state_revision="10:0:bad-status-pair",
            )
    finally:
        conn.close()


def test_operation_execution_repository_requires_explicit_plan_identity(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        with pytest.raises(TypeError, match="source_table"):
            OperationExecutionEvent(
                id=None,
                schedule_version=1,
                schedule_id=100,
                op_id=10,
                batch_id="B1",
                event_type=EXECUTION_EVENT_START,
                reported_status="processing",
                event_time="2026-05-01 08:10:00",
            )
        with pytest.raises(ValueError, match="source_table"):
            repo.insert_event(_event(source_table=None, idempotency_key="missing-source"))
        with pytest.raises(ValueError, match="effective_plan_role"):
            repo.insert_event(_event(effective_plan_role=None, idempotency_key="missing-role"))
    finally:
        conn.close()


def test_operation_execution_repository_rejects_batch_id_that_does_not_match_op(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        with pytest.raises(ValueError, match="schedule identity"):
            repo.insert_event(_event(batch_id="B2", idempotency_key="wrong-batch"))
        created = repo.insert_event(_event(idempotency_key="correct-batch"))
        assert created.batch_id == "B1"
    finally:
        conn.close()


def test_operation_execution_repository_rejects_schedule_identity_mismatch(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        _seed_second_schedule(conn)
        repo = OperationExecutionEventRepo(conn)

        with pytest.raises(ValueError, match="schedule identity"):
            repo.insert_event(
                _event(
                    schedule_version=2,
                    schedule_id=100,
                    idempotency_key="wrong-schedule-version",
                )
            )
        with pytest.raises(ValueError, match="schedule identity"):
            repo.insert_event(
                _event(
                    schedule_version=1,
                    schedule_id=101,
                    idempotency_key="wrong-schedule-id",
                )
            )
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

        _assert_repository_readbacks(repo, start, exception, finish)
        _assert_completed_execution_state(repo.aggregate_states_by_scopes([_scope(1, 100)])[_scope(1, 100)], finish, exception)
    finally:
        conn.close()


def test_operation_execution_repository_rejects_unscoped_op_reads(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        repo.insert_event(_event())
        conn.commit()

        with pytest.raises(ValueError, match="完整计划身份"):
            repo.list_events_by_op_id(10)
        with pytest.raises(ValueError, match="完整计划身份"):
            repo.list_events_by_op_ids([10])
        with pytest.raises(ValueError, match="完整计划身份"):
            repo.list_latest_events_by_op_ids([10])
        with pytest.raises(ValueError, match="完整计划身份"):
            repo.list_latest_exception_events_by_op_ids([10])
        with pytest.raises(ValueError, match="完整计划身份"):
            repo.aggregate_states_by_op_ids([10])
        with pytest.raises(ValueError, match="完整计划身份"):
            repo.state_revision_for_op(10)
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
            repo.insert_event(
                _event(
                    idempotency_key="key-duplicate-revision",
                    request_fingerprint="fingerprint-duplicate-revision",
                )
            )
        _seed_second_schedule(conn)
        repo.insert_event(_event(schedule_version=2, schedule_id=101, idempotency_key="key-other-version"))
    finally:
        conn.close()
