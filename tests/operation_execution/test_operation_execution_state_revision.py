"""开工反馈幂等复用，过期修订与非正式方案拒绝写入。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.errors import AppError
from core.infrastructure.database import get_connection
from core.infrastructure.operation_execution_event_data_contract import operation_execution_event_data_issues
from core.models.schedule_plan_role import ROLE_BASELINE_BEST
from core.services.scheduler.execution.operation_execution_scope_read import scope_from_feedback_context
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS
from tests.operation_execution.operation_execution_state_revision_support import (
    _connect,
    _context,
    _event_count,
    _seed_plan,
)


def test_start_operation_uses_previous_revision_and_reuses_same_idempotency_key(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = OperationExecutionFeedbackService(conn)

        initial_scope = scope_from_feedback_context(_context())
        initial = service.get_execution_state_for_scopes([initial_scope])[initial_scope]
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
        assert result.event.request_fingerprint is None
        assert result.state.current_status == "processing"
        assert result.state.current_status_label == "生产中"
        assert result.state_revision == f"10:1:{result.event.id}"
        assert result.state.latest_exception_event_id is None
        assert result.state.latest_exception_impact_minutes_label is None
        assert result.state.latest_exception_suggest_reschedule is False
        assert result.state.latest_exception_suggest_reschedule_label is None
        assert _event_count(conn) == 1
        assert operation_execution_event_data_issues(conn) == []

        legacy_fingerprint = "legacy-recorded-request"
        conn.execute("UPDATE OperationExecutionEvents SET request_fingerprint=? WHERE id=?",
                     (legacy_fingerprint, result.event.id))
        conn.commit()

        reused = service.start_operation(
            _context(expected_state_revision=initial.state_revision),
            event_time="2026-05-01 08:10:00",
            operator_id="O1",
            machine_id="M1",
            remark="开始加工",
        )
        assert reused.idempotency_reused is True
        assert reused.event.id == result.event.id
        assert reused.event.request_fingerprint == legacy_fingerprint
        assert reused.state_revision == result.state_revision
        assert _event_count(conn) == 1

        with pytest.raises(AppError) as changed:
            service.start_operation(
                _context(expected_state_revision=initial.state_revision),
                event_time="2026-05-01 08:10:00", operator_id="O1", machine_id="M1", remark="改变的反馈内容",
            )
        assert changed.value.details["reason"] == "idempotency_conflict"

        for changed_type in (True, 1.0):
            with pytest.raises(AppError) as typed_conflict:
                service._resolve_idempotent_existing(
                    replace(reused.event, schedule_version=changed_type),
                    context=_context(expected_state_revision=initial.state_revision), action="start",
                    payload={"event_time": "2026-05-01 08:10:00", "actual_operator_id": "O1",
                             "actual_machine_id": "M1", "remark": "开始加工"},
                )
            assert typed_conflict.value.details["reason"] == "idempotency_conflict"
        assert service.get_event_by_idempotency_key(_context().idempotency_key).request_fingerprint == legacy_fingerprint
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
