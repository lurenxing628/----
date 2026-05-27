from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


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


def _context(**overrides) -> ExecutionFeedbackContext:
    data = {
        "schedule_version": 1,
        "schedule_id": 100,
        "op_id": 10,
        "expected_state_revision": "10:0:0",
        "created_by": "张三",
        "idempotency_key": "start-key",
        "requested_plan_role": ROLE_ADOPTED,
        "source_table": SOURCE_SCHEDULE,
        "effective_plan_role": ROLE_ADOPTED,
        "scenario_id": None,
    }
    data.update(overrides)
    return ExecutionFeedbackContext(**data)


def _event_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents").fetchone()
    return int(row["count"])


def test_start_operation_uses_previous_revision_and_reuses_same_idempotency_key(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)

        initial = service.get_execution_state([10])[10]
        assert initial.state_revision == "10:0:0"

        result = service.start_operation(
            _context(expected_state_revision=initial.state_revision),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )
        assert result.idempotency_reused is False
        assert result.event.previous_state_revision == "10:0:0"
        assert result.event.request_fingerprint
        assert result.state.current_status == "processing"
        assert result.state.current_status_label == "生产中"
        assert result.state_revision == f"10:1:{result.event.id}"
        assert _event_count(conn) == 1

        reused = service.start_operation(
            _context(expected_state_revision=initial.state_revision),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )
        assert reused.idempotency_reused is True
        assert reused.event.id == result.event.id
        assert reused.state_revision == result.state_revision
        assert _event_count(conn) == 1
    finally:
        conn.close()


def test_same_idempotency_key_with_different_payload_is_conflict_before_revision_check(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        service.start_operation(
            _context(),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )

        with pytest.raises(AppError) as exc_info:
            service.start_operation(
                _context(expected_state_revision="10:0:0"),
                event_time="2026-05-01 08:11:00",
                operator_id="O1",
                machine_id="M1",
                remark="开始加工",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "idempotency_conflict"
        assert _event_count(conn) == 1
    finally:
        conn.close()


def test_stale_state_revision_and_non_official_plan_do_not_write_events(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        first = service.start_operation(
            _context(),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
        )
        assert first.state_revision.startswith("10:1:")

        with pytest.raises(AppError) as stale:
            service.start_operation(
                _context(idempotency_key="start-key-2", expected_state_revision="10:0:0"),
                event_time="2026-05-01 08:20:00",
                operator_id="O1",
                machine_id="M1",
            )
        assert stale.value.code.value == "6003"
        assert stale.value.details["reason"] == "stale_state_revision"

        with pytest.raises(AppError) as not_official:
            service.start_operation(
                _context(
                    idempotency_key="candidate-key",
                    requested_plan_role=ROLE_BASELINE_BEST,
                    source_table=SOURCE_CANDIDATE_ROWS,
                    effective_plan_role=ROLE_BASELINE_BEST,
                    expected_state_revision=first.state_revision,
                ),
                event_time="2026-05-01 08:30:00",
                operator_id="O1",
                machine_id="M1",
            )
        assert not_official.value.code.value == "6003"
        assert not_official.value.details["reason"] == "not_current_official_plan"
        assert _event_count(conn) == 1
    finally:
        conn.close()


def test_schedule_row_must_match_version_schedule_and_operation(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)

        with pytest.raises(AppError) as exc_info:
            service.start_operation(
                _context(op_id=999, idempotency_key="bad-op", expected_state_revision="999:0:0"),
                event_time="2026-05-01 08:10:00",
                operator_id="O1",
                machine_id="M1",
            )
        assert exc_info.value.code.value in ("1002", "6003")
        assert _event_count(conn) == 0
    finally:
        conn.close()


def test_finish_requires_operation_to_be_started(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)

        with pytest.raises(AppError) as exc_info:
            service.finish_operation(
                _context(idempotency_key="finish-before-start"),
                event_time="2026-05-01 09:00:00",
                quantity_done=10,
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "invalid_state_transition"
        assert exc_info.value.details["current_status_label"] == "待开工"
        assert exc_info.value.details["action_label"] == "完工"
        assert _event_count(conn) == 0
    finally:
        conn.close()


def test_completed_operation_cannot_start_again(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        started = service.start_operation(
            _context(),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
        )
        finished = service.finish_operation(
            _context(
                idempotency_key="finish-key",
                expected_state_revision=started.state_revision,
            ),
            event_time="2026-05-01 09:00:00",
            quantity_done=10,
        )

        with pytest.raises(AppError) as exc_info:
            service.start_operation(
                _context(
                    idempotency_key="restart-key",
                    expected_state_revision=finished.state_revision,
                ),
                event_time="2026-05-01 09:10:00",
                operator_id="O1",
                machine_id="M1",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "invalid_state_transition"
        assert exc_info.value.details["current_status_label"] == "已完工"
        assert exc_info.value.details["action_label"] == "开工"
        assert _event_count(conn) == 2
    finally:
        conn.close()


def test_pause_resume_exception_and_finish_state_flow_is_aggregated(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        started = service.start_operation(
            _context(),
            event_time="2026-05-01 08:00:00",
            operator_id="O1",
            machine_id="M1",
        )
        paused = service.pause_operation(
            _context(idempotency_key="pause-key", expected_state_revision=started.state_revision),
            event_time="2026-05-01 08:20:00",
            reason_code="equipment",
            remark="设备需要检查",
        )
        assert paused.state.current_status == "paused"
        assert paused.state.current_status_label == "已暂停"
        assert paused.state.pause_duration_minutes == 0

        resumed = service.resume_operation(
            _context(idempotency_key="resume-key", expected_state_revision=paused.state_revision),
            event_time="2026-05-01 08:35:00",
            remark="继续生产",
        )
        assert resumed.state.current_status == "processing"
        assert resumed.state.pause_duration_minutes == 15
        assert resumed.state.last_event_action_label == "继续生产"

        exception = service.report_exception(
            _context(idempotency_key="exception-key", expected_state_revision=resumed.state_revision),
            event_time="2026-05-01 08:45:00",
            reason_code="equipment",
            severity="high",
            impact_minutes=30,
            affected_machine_id="M2",
            affected_operator_id="O2",
            handling_status="new",
            suggest_reschedule="yes",
            remark="设备突然停了",
        )
        assert exception.state.current_status == "exception"
        assert exception.event.event_type == "exception"
        assert exception.state.last_event_action_label == "报异常"
        assert exception.state.latest_exception_reason_label == "设备问题"
        assert exception.state.latest_exception_severity_label == "严重"
        assert exception.state.latest_exception_affected_machine_label == "二号设备"
        assert exception.state.latest_exception_affected_operator_label == "李四"
        assert exception.state.latest_exception_suggest_reschedule_label == "建议重新排程"

        resumed_after_exception = service.resume_operation(
            _context(
                idempotency_key="resume-after-exception-key",
                expected_state_revision=exception.state_revision,
            ),
            event_time="2026-05-01 09:00:00",
        )
        assert resumed_after_exception.state.current_status == "processing"
        assert resumed_after_exception.state.latest_exception_event_id == exception.event.id

        finished = service.finish_operation(
            _context(idempotency_key="finish-after-exception-key", expected_state_revision=resumed_after_exception.state_revision),
            event_time="2026-05-01 09:30:00",
            quantity_done=10,
            remark="已完工",
        )
        assert finished.state.current_status == "completed"
        assert finished.state.actual_start_time == "2026-05-01 08:00:00"
        assert finished.state.actual_end_time == "2026-05-01 09:30:00"
        assert finished.state.actual_duration_minutes == 90
        assert finished.state.pause_duration_minutes == 15
        assert finished.state.latest_exception_event_id == exception.event.id
        assert finished.state.latest_exception_remark == "设备突然停了"
        assert _event_count(conn) == 6
    finally:
        conn.close()


@pytest.mark.parametrize(
    "method_name,kwargs,action_label",
    [
        ("pause_operation", {"event_time": "2026-05-01 08:10:00", "reason_code": "equipment"}, "暂停"),
        ("resume_operation", {"event_time": "2026-05-01 08:10:00"}, "继续生产"),
        (
            "report_exception",
            {"event_time": "2026-05-01 08:10:00", "reason_code": "equipment", "severity": "high"},
            "报异常",
        ),
    ],
)
def test_not_started_operation_rejects_non_start_actions(tmp_path: Path, method_name: str, kwargs, action_label: str) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        method = getattr(service, method_name)

        with pytest.raises(AppError) as exc_info:
            method(
                _context(idempotency_key=f"{method_name}-not-started"),
                **kwargs,
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "invalid_state_transition"
        assert exc_info.value.details["current_status_label"] == "待开工"
        assert exc_info.value.details["action_label"] == action_label
        assert _event_count(conn) == 0
    finally:
        conn.close()
