"""回归测试：OperationExecutionFeedbackService 的开工→暂停→继续→报异常→完工状态流聚合——校验暂停时长累计、异常各字段标签（工种/设备/人员身份、严重度、建议重排）、完工后保留最近异常信息；并守护写库前的必填/非法字段校验（AppError 1001）、事件时间倒退与未开工时非开工动作的状态机拒绝（AppError 6003）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from tests.operation_execution_state_revision_support import _connect, _context, _event_count, _seed_plan


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
