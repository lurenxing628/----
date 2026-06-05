from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.operation_execution_scope_read import scope_from_feedback_context
from core.services.scheduler.schedule_plan_query_service import ROLE_BASELINE_BEST
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS
from tests.operation_execution_state_revision_support import (
    _connect,
    _context,
    _event_count,
    _event_count_from_path,
    _prepare_db,
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
