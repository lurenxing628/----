from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.operation_execution_event_data_contract import (
    operation_execution_event_data_issues,
    operation_execution_event_sequence_issues,
)
from core.models.operation_execution_event import (
    EXECUTION_EVENT_FINISH,
    OperationExecutionEvent,
    validate_operation_execution_event_sequence,
)
from core.services.scheduler.operation_execution_scope_read import scope_from_plan_row
from core.services.scheduler.resource_dispatch_execution_tokens import execution_task_key
from data.repositories import OperationExecutionEventRepo
from data.repositories.operation_execution_state_builder import build_operation_execution_state
from tests.regression_operation_execution_event_foundation import (
    _connect,
    _event,
    _insert_raw_event,
    _scope,
    _seed_plan,
    _seed_second_schedule,
)


def test_operation_execution_scope_identity_rejects_bool_and_fractional_integers() -> None:
    with pytest.raises(ValueError, match="schedule_id"):
        OperationExecutionEvent.from_row(
            _event(
                schedule_version=2,
                schedule_id=True,
            )
        )
    with pytest.raises(ValueError, match="op_id"):
        OperationExecutionEvent.from_row(
            _event(
                schedule_version=2,
                schedule_id=100,
                op_id=10.9,
            )
        )
    with pytest.raises(ValueError, match="schedule_id"):
        execution_task_key({"schedule_id": 100.9, "op_id": 10, "batch_id": "B1"})
    with pytest.raises(ValueError, match="计划行缺少现场执行身份字段"):
        scope_from_plan_row(
            {"schedule_id": True, "op_id": 10, "version": 2, "batch_id": "B1"},
            {"source_table": "schedule", "effective_plan_role": "adopted"},
        )


def test_operation_execution_event_sequence_contract_rejects_invalid_flows() -> None:
    validate_operation_execution_event_sequence(
        [
            _event(id=1),
            _event(
                id=2,
                event_type=EXECUTION_EVENT_FINISH,
                reported_status="completed",
                event_time="2026-05-01 09:00:00",
                previous_state_revision="10:1:1",
            ),
        ]
    )
    with pytest.raises(ValueError, match="cannot follow"):
        validate_operation_execution_event_sequence(
            [
                _event(id=1, event_type=EXECUTION_EVENT_FINISH, reported_status="completed"),
            ]
        )
    with pytest.raises(ValueError, match="cannot follow"):
        validate_operation_execution_event_sequence(
            [
                _event(id=1),
                _event(
                    id=2,
                    event_type=EXECUTION_EVENT_FINISH,
                    reported_status="completed",
                    event_time="2026-05-01 09:00:00",
                    previous_state_revision="10:1:1",
                ),
                _event(id=3, event_time="2026-05-01 09:10:00", previous_state_revision="10:2:2"),
            ]
        )
    with pytest.raises(ValueError, match="moved backwards"):
        validate_operation_execution_event_sequence(
            [
                _event(id=1, event_time="2026-05-01 08:30:00"),
                _event(
                    id=2,
                    event_type=EXECUTION_EVENT_FINISH,
                    reported_status="completed",
                    event_time="2026-05-01 08:20:00",
                    previous_state_revision="10:1:1",
                ),
            ]
        )

    with pytest.raises(ValueError, match="previous_state_revision"):
        validate_operation_execution_event_sequence(
            [
                _event(id=1),
                _event(
                    id=2,
                    event_type=EXECUTION_EVENT_FINISH,
                    reported_status="completed",
                    event_time="2026-05-01 09:00:00",
                    previous_state_revision="WRONG-REVISION",
                ),
            ]
        )


def test_operation_execution_repository_rejects_invalid_event_sequence(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        with pytest.raises(ValueError, match="event sequence"):
            repo.insert_event(
                _event(
                    event_type=EXECUTION_EVENT_FINISH,
                    reported_status="completed",
                    idempotency_key="finish-without-start",
                    request_fingerprint="finish-without-start",
                )
            )
        start = repo.insert_event(_event())
        finish = repo.insert_event(
            _event(
                event_type=EXECUTION_EVENT_FINISH,
                reported_status="completed",
                event_time="2026-05-01 09:00:00",
                idempotency_key="finish-ok",
                request_fingerprint="finish-ok",
                previous_state_revision=f"10:1:{start.id}",
            )
        )
        with pytest.raises(ValueError, match="event sequence"):
            repo.insert_event(
                _event(
                    event_time="2026-05-01 09:10:00",
                    idempotency_key="start-after-finish",
                    request_fingerprint="start-after-finish",
                    previous_state_revision=f"10:2:{finish.id}",
                )
            )
    finally:
        conn.close()


def test_operation_execution_repository_rejects_wrong_previous_state_revision(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        repo.insert_event(_event())

        with pytest.raises(ValueError, match="previous_state_revision"):
            repo.insert_event(
                _event(
                    event_type=EXECUTION_EVENT_FINISH,
                    reported_status="completed",
                    event_time="2026-05-01 09:00:00",
                    quantity_done=10,
                    idempotency_key="finish-wrong-revision",
                    request_fingerprint="finish-wrong-revision",
                    previous_state_revision="WRONG-REVISION",
                )
            )
    finally:
        conn.close()


def test_operation_execution_state_builder_rejects_raw_invalid_event_sequence(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        _insert_raw_event(
            conn,
            event_type=EXECUTION_EVENT_FINISH,
            reported_status="completed",
            quantity_done=10,
            idempotency_key="raw-finish-without-start",
            request_fingerprint="raw-finish-without-start",
        )
        conn.commit()
        repo = OperationExecutionEventRepo(conn)

        with pytest.raises(ValueError, match="event sequence"):
            repo.aggregate_states_by_scopes([_scope(1, 100)])
        with pytest.raises(ValueError, match="event sequence"):
            repo.list_events_by_scope(_scope(1, 100))
        with pytest.raises(ValueError, match="event sequence"):
            repo.get_by_idempotency_key("raw-finish-without-start")
        issues = operation_execution_event_sequence_issues(conn)
        assert issues and "bad_sequence" in issues[0]
    finally:
        conn.close()


def test_operation_execution_sequence_rejects_mixed_plan_scope() -> None:
    start = _event(id=1)
    finish_from_other_schedule = _event(
        id=2,
        schedule_version=2,
        schedule_id=101,
        event_type=EXECUTION_EVENT_FINISH,
        reported_status="completed",
        event_time="2026-05-01 09:00:00",
        previous_state_revision="10:1:1",
    )

    with pytest.raises(ValueError, match="scope changed"):
        validate_operation_execution_event_sequence([start, finish_from_other_schedule])
    with pytest.raises(ValueError, match="scope changed"):
        build_operation_execution_state(
            op_id=10,
            batch_id="B1",
            events=[
                OperationExecutionEvent.from_row(start),
                OperationExecutionEvent.from_row(finish_from_other_schedule),
            ],
            machine_resources={},
            operator_resources={},
        )


def test_operation_execution_repository_rejects_bad_numeric_text_on_read(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        _insert_raw_event(
            conn,
            impact_minutes="abc",
            idempotency_key="raw-bad-impact",
            request_fingerprint="raw-bad-impact",
        )
        conn.commit()
        repo = OperationExecutionEventRepo(conn)

        with pytest.raises(ValueError, match="impact_minutes"):
            repo.list_events_by_scope(_scope(1, 100))
        with pytest.raises(ValueError, match="impact_minutes"):
            repo.aggregate_states_by_scopes([_scope(1, 100)])
    finally:
        conn.close()


def test_operation_execution_data_contract_rejects_fractional_integer_storage(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        _insert_raw_event(
            conn,
            quantity_done=1.5,
            idempotency_key="raw-fractional-quantity",
            request_fingerprint="raw-fractional-quantity",
            previous_state_revision="10:0:fractional-quantity",
        )
        _insert_raw_event(
            conn,
            impact_minutes=1.5,
            idempotency_key="raw-fractional-impact",
            request_fingerprint="raw-fractional-impact",
            previous_state_revision="10:0:fractional-impact",
        )
        conn.commit()

        issues = operation_execution_event_data_issues(conn, limit=4)

        assert any("quantity_done" in issue for issue in issues)
        assert any("impact_minutes" in issue for issue in issues)
    finally:
        conn.close()


def test_operation_execution_scope_keeps_versions_separate(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        _seed_second_schedule(conn)
        repo = OperationExecutionEventRepo(conn)
        version_one = repo.insert_event(_event())
        version_two = repo.insert_event(
            _event(
                schedule_version=2,
                schedule_id=101,
                actual_machine_id="M2",
                actual_operator_id="O2",
                idempotency_key="key-start-v2",
                request_fingerprint="fingerprint-start-v2",
            )
        )
        conn.commit()

        states = repo.aggregate_states_by_scopes([_scope(1, 100), _scope(2, 101)])

        assert states[_scope(1, 100)].actual_machine_display_label == "一号设备"
        assert states[_scope(2, 101)].actual_machine_display_label == "二号设备"
        assert repo.state_revision_for_scope(_scope(1, 100)) == f"10:1:{version_one.id}"
        assert repo.state_revision_for_scope(_scope(2, 101)) == f"10:1:{version_two.id}"
    finally:
        conn.close()


def test_operation_execution_state_keeps_fractional_minutes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        repo = OperationExecutionEventRepo(conn)
        start = repo.insert_event(_event(event_time="2026-05-01 08:00:30"))
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

        state = repo.aggregate_states_by_scopes([_scope(1, 100)])[_scope(1, 100)]
        assert state.last_event_id == finish.id
        assert state.actual_duration_minutes == 1.5
        assert state.pause_duration_minutes == 0.5
    finally:
        conn.close()
