"""回归测试：现场异常工序阻断普通自动重排——某工序 report_exception 后，ScheduleService.run_schedule 应抛 AppError（code 6003、reason=execution_exception_blocks_auto_reschedule、details.op_ids=[10]、提示含「异常中/先处理现场异常」且不泄露原始 op_id），且不写库（计数与 schedule 行不变）；而暂停（pause）工序在最小重排护栏下被锁定固定（保持原 start/machine/operator、lock_status=locked，后继工序顺延）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_service import ScheduleService
from tests.regression_scheduler_reschedule_execution_minimum_guardrails import (
    _connect,
    _context,
    _counts,
    _schedule_rows,
    _seed_two_operation_plan,
)


def test_exception_operation_blocks_ordinary_auto_reschedule_without_writing(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        started = feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.report_exception(
            _context(revision=started.state_revision, key="exception-key"),
            event_time="2026-05-01 08:30:00",
            reason_code="equipment",
            severity="high",
            impact_minutes=30,
            affected_machine_id="M1",
            affected_operator_id="O1",
            handling_status="new",
            suggest_reschedule="yes",
            remark="设备异常，等待处理",
        )
        before_counts = _counts(conn)
        before_rows = _schedule_rows(conn, 1)

        with pytest.raises(AppError) as exc_info:
            ScheduleService(conn).run_schedule(
                ["B1"],
                start_dt="2026-05-01 08:00:00",
                created_by="pytest",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_exception_blocks_auto_reschedule"
        assert exc_info.value.details["op_ids"] == [10]
        assert "异常中" in exc_info.value.message
        assert "先处理现场异常" in exc_info.value.message
        assert "10" not in exc_info.value.message
        assert _counts(conn) == before_counts
        assert _schedule_rows(conn, 1) == before_rows
    finally:
        conn.close()


def test_paused_operation_is_fixed_in_minimum_reschedule_guardrail(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        started = feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:20:00",
            operator_id="O1",
            machine_id="M1",
        )
        feedback.pause_operation(
            _context(revision=started.state_revision, key="pause-key"),
            event_time="2026-05-01 08:35:00",
            reason_code="equipment",
            remark="设备需要检查",
        )

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
        )

        rows = _schedule_rows(conn, int(result["version"]))
        assert rows[10]["start_time"] == "2026-05-01 08:20:00"
        assert rows[10]["machine_id"] == "M1"
        assert rows[10]["operator_id"] == "O1"
        assert rows[10]["lock_status"] == "locked"
        assert rows[20]["start_time"] >= rows[10]["end_time"]
    finally:
        conn.close()
