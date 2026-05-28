from __future__ import annotations

import sqlite3
import threading
import time
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


def _prepare_db(tmp_path: Path, name: str = "aps.db") -> Path:
    db_path = tmp_path / name
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    conn = get_connection(str(db_path))
    try:
        _seed_plan(conn)
    finally:
        conn.close()
    return db_path


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
        "batch_id": "B1",
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


def _event_count_from_path(db_path: Path) -> int:
    conn = get_connection(str(db_path))
    try:
        return _event_count(conn)
    finally:
        conn.close()


def test_start_operation_uses_previous_revision_and_reuses_same_idempotency_key(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)

        initial = service.get_execution_state([10])[10]
        assert initial.state_revision == "10:0:0"
        assert initial.latest_exception_event_id is None
        assert initial.latest_exception_impact_minutes_label is None
        assert initial.latest_exception_suggest_reschedule is False
        assert initial.latest_exception_suggest_reschedule_label is None

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
        assert result.state.latest_exception_event_id is None
        assert result.state.latest_exception_impact_minutes_label is None
        assert result.state.latest_exception_suggest_reschedule is False
        assert result.state.latest_exception_suggest_reschedule_label is None
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


def test_idempotency_is_rechecked_inside_transaction_before_revision_check(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        first = service.start_operation(
            _context(),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )

        original_lookup = service.event_repo.get_by_idempotency_key
        calls = {"count": 0}

        def lookup_with_first_miss(idempotency_key: str):
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return original_lookup(idempotency_key)

        monkeypatch.setattr(service.event_repo, "get_by_idempotency_key", lookup_with_first_miss)

        reused = service.start_operation(
            _context(expected_state_revision="10:0:0"),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )

        assert reused.idempotency_reused is True
        assert reused.event.id == first.event.id
        assert reused.state_revision == first.state_revision
        assert calls["count"] >= 2
        assert _event_count(conn) == 1
    finally:
        conn.close()


def _record_start_from_new_connection(db_path: Path, context: ExecutionFeedbackContext, out: list) -> None:
    conn = get_connection(str(db_path))
    try:
        service = OperationExecutionFeedbackService(conn)
        result = service.start_operation(
            context,
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )
        out.append(("ok", result.idempotency_reused, result.state_revision))
    except AppError as exc:
        out.append(("error", exc.code.value, (exc.details or {}).get("reason")))
    finally:
        conn.close()


def test_concurrent_same_idempotency_waits_and_reuses_existing_event(tmp_path: Path) -> None:
    db_path = _prepare_db(tmp_path, "concurrent_same_key.db")
    holder = get_connection(str(db_path))
    try:
        holder.execute("BEGIN IMMEDIATE")
        holder_service = OperationExecutionFeedbackService(holder)
        first = holder_service.start_operation(
            _context(idempotency_key="concurrent-same-key"),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )

        results = []
        thread = threading.Thread(
            target=_record_start_from_new_connection,
            args=(db_path, _context(idempotency_key="concurrent-same-key"), results),
        )
        thread.start()
        time.sleep(0.1)
        holder.commit()
        thread.join(timeout=3)

        assert not thread.is_alive()
        assert results == [("ok", True, first.state_revision)]
        assert _event_count_from_path(db_path) == 1
    finally:
        if holder.in_transaction:
            holder.rollback()
        holder.close()


def test_concurrent_different_idempotency_reports_stale_state_revision(tmp_path: Path) -> None:
    db_path = _prepare_db(tmp_path, "concurrent_different_key.db")
    holder = get_connection(str(db_path))
    try:
        holder.execute("BEGIN IMMEDIATE")
        holder_service = OperationExecutionFeedbackService(holder)
        holder_service.start_operation(
            _context(idempotency_key="concurrent-winner"),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )

        results = []
        thread = threading.Thread(
            target=_record_start_from_new_connection,
            args=(db_path, _context(idempotency_key="concurrent-loser"), results),
        )
        thread.start()
        time.sleep(0.1)
        holder.commit()
        thread.join(timeout=3)

        assert not thread.is_alive()
        assert results == [("error", "6003", "stale_state_revision")]
        assert _event_count_from_path(db_path) == 1
    finally:
        if holder.in_transaction:
            holder.rollback()
        holder.close()


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
        assert exception.state.latest_exception_affected_machine_label == "M2 二号设备"
        assert exception.state.latest_exception_affected_machine_display_label == "二号设备"
        assert exception.state.latest_exception_affected_machine_identity_label == "M2 二号设备"
        assert exception.state.latest_exception_affected_operator_label == "O2 李四"
        assert exception.state.latest_exception_affected_operator_display_label == "李四"
        assert exception.state.latest_exception_affected_operator_identity_label == "O2 李四"
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


def test_exception_while_paused_closes_pause_duration(tmp_path: Path) -> None:
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
            _context(idempotency_key="pause-before-exception", expected_state_revision=started.state_revision),
            event_time="2026-05-01 08:20:00",
            reason_code="equipment",
            remark="设备需要检查",
        )

        exception = service.report_exception(
            _context(idempotency_key="exception-while-paused", expected_state_revision=paused.state_revision),
            event_time="2026-05-01 08:30:00",
            reason_code="equipment",
            severity="high",
            impact_minutes=30,
            handling_status=None,
            remark="设备异常",
        )
        assert exception.state.current_status == "exception"
        assert exception.state.pause_duration_minutes == 10
        assert exception.state.latest_exception_handling_status is None
        assert exception.state.latest_exception_handling_status_label == "刚上报"

        resumed = service.resume_operation(
            _context(idempotency_key="resume-after-paused-exception", expected_state_revision=exception.state_revision),
            event_time="2026-05-01 09:00:00",
        )
        assert resumed.state.current_status == "processing"
        assert resumed.state.pause_duration_minutes == 10
        assert _event_count(conn) == 4
    finally:
        conn.close()


def test_finish_without_exception_keeps_exception_fields_empty(tmp_path: Path) -> None:
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
        finished = service.finish_operation(
            _context(idempotency_key="finish-without-exception", expected_state_revision=started.state_revision),
            event_time="2026-05-01 09:00:00",
            quantity_done=10,
        )

        assert finished.state.current_status == "completed"
        assert finished.state.latest_exception_event_id is None
        assert finished.state.latest_exception_reason_label is None
        assert finished.state.latest_exception_impact_minutes_label is None
        assert finished.state.latest_exception_suggest_reschedule is False
        assert finished.state.latest_exception_suggest_reschedule_label is None
        assert _event_count(conn) == 2
    finally:
        conn.close()


def test_execution_feedback_requires_pause_and_exception_details_before_write(tmp_path: Path) -> None:
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

        with pytest.raises(AppError) as missing_pause_reason:
            service.pause_operation(
                _context(idempotency_key="pause-missing-reason", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:10:00",
                reason_code="",
            )
        assert missing_pause_reason.value.code.value == "1001"
        assert missing_pause_reason.value.details["reason"] == "missing_required_field"
        assert missing_pause_reason.value.details["field"] == "reason_code"

        with pytest.raises(AppError) as missing_pause_detail:
            service.pause_operation(
                _context(idempotency_key="pause-missing-detail", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:12:00",
                reason_code="equipment",
            )
        assert missing_pause_detail.value.code.value == "1001"
        assert missing_pause_detail.value.details["reason"] == "missing_required_field"
        assert missing_pause_detail.value.details["field"] == "remark"

        with pytest.raises(AppError) as missing_exception_reason:
            service.report_exception(
                _context(idempotency_key="exception-missing-reason", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:15:00",
                reason_code="",
                severity="high",
            )
        assert missing_exception_reason.value.code.value == "1001"
        assert missing_exception_reason.value.details["reason"] == "missing_required_field"
        assert missing_exception_reason.value.details["field"] == "reason_code"

        with pytest.raises(AppError) as missing_exception_severity:
            service.report_exception(
                _context(idempotency_key="exception-missing-severity", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:20:00",
                reason_code="equipment",
                severity="",
                remark="设备异常",
            )
        assert missing_exception_severity.value.code.value == "1001"
        assert missing_exception_severity.value.details["reason"] == "missing_required_field"
        assert missing_exception_severity.value.details["field"] == "severity"

        with pytest.raises(AppError) as missing_exception_detail:
            service.report_exception(
                _context(idempotency_key="exception-missing-detail", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:25:00",
                reason_code="equipment",
                severity="high",
            )
        assert missing_exception_detail.value.code.value == "1001"
        assert missing_exception_detail.value.details["reason"] == "missing_required_field"
        assert missing_exception_detail.value.details["field"] == "remark"
        assert _event_count(conn) == 1
    finally:
        conn.close()


@pytest.mark.parametrize(
    "override,field",
    [
        ({"reason_code": "bad_reason"}, "reason_code"),
        ({"severity": "bad_severity"}, "severity"),
        ({"impact_minutes": -1}, "impact_minutes"),
        ({"affected_machine_id": "NO_SUCH_MACHINE"}, "affected_machine_id"),
        ({"affected_operator_id": "NO_SUCH_OPERATOR"}, "affected_operator_id"),
        ({"handling_status": "bad_handling"}, "handling_status"),
        ({"suggest_reschedule": "maybe"}, "suggest_reschedule"),
    ],
)
def test_exception_feedback_rejects_invalid_fields_before_database_write(tmp_path: Path, override, field: str) -> None:
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
        payload = {
            "event_time": "2026-05-01 08:15:00",
            "reason_code": "equipment",
            "severity": "high",
            "impact_minutes": 10,
            "affected_machine_id": "M2",
            "affected_operator_id": "O2",
            "handling_status": "new",
            "suggest_reschedule": 0,
            "remark": "设备异常",
        }
        payload.update(override)

        with pytest.raises(AppError) as exc_info:
            service.report_exception(
                _context(
                    idempotency_key=f"invalid-exception-{field}",
                    expected_state_revision=started.state_revision,
                ),
                **payload,
            )

        assert exc_info.value.code.value == "1001"
        assert exc_info.value.details["reason"] == "invalid_field_value"
        assert exc_info.value.details["field"] == field
        assert exc_info.value.details["field_label"]
        assert "db_message" not in exc_info.value.details
        assert _event_count(conn) == 1
    finally:
        conn.close()


def test_execution_feedback_rejects_event_time_before_last_feedback(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)
        started = service.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )

        with pytest.raises(AppError) as pause_error:
            service.pause_operation(
                _context(idempotency_key="pause-before-start-time", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:10:00",
                reason_code="equipment",
                remark="设备需要检查",
            )
        assert pause_error.value.code.value == "6003"
        assert pause_error.value.details["reason"] == "invalid_state_transition"
        assert pause_error.value.details["action_label"] == "暂停"

        with pytest.raises(AppError) as finish_error:
            service.finish_operation(
                _context(idempotency_key="finish-before-start-time", expected_state_revision=started.state_revision),
                event_time="2026-05-01 08:15:00",
                quantity_done=10,
            )
        assert finish_error.value.code.value == "6003"
        assert finish_error.value.details["reason"] == "invalid_state_transition"
        assert finish_error.value.details["action_label"] == "完工"
        assert _event_count(conn) == 1
    finally:
        conn.close()


@pytest.mark.parametrize(
    "method_name,kwargs,action_label",
    [
        ("pause_operation", {"event_time": "2026-05-01 08:10:00", "reason_code": "equipment", "remark": "设备需要检查"}, "暂停"),
        ("resume_operation", {"event_time": "2026-05-01 08:10:00"}, "继续生产"),
        (
            "report_exception",
            {"event_time": "2026-05-01 08:10:00", "reason_code": "equipment", "severity": "high", "remark": "设备异常"},
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
