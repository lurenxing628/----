"""回归测试：工序执行事件的 event_time 契约——normalize_operation_event_time / OperationExecutionEvent.from_row / 仓储 insert_event / 状态构建器 / schema CHECK 都必须归一化合法时间（如 2026/05/01T08:10）并拒绝非法日历值（如 2026-02-30）、event_type 与 reported_status 不匹配、以及非当前正式口径（candidate_rows 来源、baseline_best 角色、scenario 预览）的事件。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.operation_execution_event import (
    EXECUTION_EVENT_START,
    OperationExecutionEvent,
    normalize_operation_event_time,
)
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from data.repositories.operation_execution_state_builder import build_operation_execution_state
from tests._support.paths import REPO_ROOT
from tests.operation_execution.operation_execution_feedback_test_support import _seed_execution_feedback_context

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "event_time_contract.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    conn = get_connection(str(db_path))
    _seed_execution_feedback_context(conn)
    conn.commit()
    return conn


def _event(**overrides):
    payload = {
        "schedule_version": 2,
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
        "idempotency_key": "event-time-key",
        "request_fingerprint": "event-time-fingerprint",
        "previous_state_revision": "10:0:0",
    }
    payload.update(overrides)
    return payload


def _insert_raw_event(conn: sqlite3.Connection, **overrides) -> None:
    payload = _event(**overrides)
    columns = ", ".join(payload)
    placeholders = ", ".join("?" for _ in payload)
    conn.execute(f"INSERT INTO OperationExecutionEvents ({columns}) VALUES ({placeholders})", tuple(payload.values()))


def test_operation_execution_event_time_model_rejects_invalid_calendar_values() -> None:
    assert normalize_operation_event_time("2026/05/01T08:10") == "2026-05-01 08:10:00"
    assert normalize_operation_event_time("2026-05-01") == "2026-05-01 00:00:00"

    with pytest.raises(ValueError, match="event_time"):
        normalize_operation_event_time("2026-02-30 08:10:00")
    with pytest.raises(ValueError, match="event_time"):
        OperationExecutionEvent.from_row(_event(event_time="not-a-date"))


def test_operation_execution_repository_normalizes_and_rejects_event_time(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        repo = OperationExecutionEventRepo(conn)
        created = repo.insert_event(_event(event_time="2026/05/01T08:10"))

        assert created.event_time == "2026-05-01 08:10:00"
        row = conn.execute("SELECT event_time FROM OperationExecutionEvents WHERE id = ?", (created.id,)).fetchone()
        assert row["event_time"] == "2026-05-01 08:10:00"
        with pytest.raises(ValueError, match="event_time"):
            repo.insert_event(_event(event_time="not-a-date", idempotency_key="bad-time"))
        with pytest.raises(ValueError, match="does not match"):
            repo.insert_event(_event(reported_status="completed", idempotency_key="bad-status-pair"))
        with pytest.raises(ValueError, match="current official"):
            repo.insert_event(_event(source_table="candidate_rows", idempotency_key="bad-source-table"))
        with pytest.raises(ValueError, match="adopted"):
            repo.insert_event(_event(effective_plan_role="baseline_best", idempotency_key="bad-plan-role"))
        with pytest.raises(ValueError, match="scenario preview"):
            repo.insert_event(_event(scenario_id="preview-1", idempotency_key="bad-scenario"))
    finally:
        conn.close()


def test_operation_execution_schema_rejects_direct_bad_event_time(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_raw_event(conn, event_time="not-a-date")
    finally:
        conn.close()


def test_operation_execution_state_builder_rejects_bad_event_time() -> None:
    event = OperationExecutionEvent(
        id=1,
        schedule_version=2,
        schedule_id=100,
        op_id=10,
        batch_id="B1",
        event_type=EXECUTION_EVENT_START,
        reported_status="processing",
        event_time="not-a-date",
        source_table="schedule",
        effective_plan_role="adopted",
    )

    with pytest.raises(ValueError, match="event_time"):
        build_operation_execution_state(
            op_id=10,
            batch_id="B1",
            events=[event],
            machine_resources={},
            operator_resources={},
        )


def test_operation_execution_event_contract_rejects_bad_status_pair() -> None:
    with pytest.raises(ValueError, match="does not match"):
        OperationExecutionEvent.from_row(_event(reported_status="completed"))

    event = OperationExecutionEvent(
        id=1,
        schedule_version=2,
        schedule_id=100,
        op_id=10,
        batch_id="B1",
        event_type=EXECUTION_EVENT_START,
        reported_status="completed",
        event_time="2026-05-01 08:10:00",
        source_table="schedule",
        effective_plan_role="adopted",
    )

    with pytest.raises(ValueError, match="does not match"):
        build_operation_execution_state(
            op_id=10,
            batch_id="B1",
            events=[event],
            machine_resources={},
            operator_resources={},
        )


def test_operation_execution_event_contract_rejects_non_official_scope() -> None:
    with pytest.raises(ValueError, match="current official"):
        OperationExecutionEvent.from_row(_event(source_table="candidate_rows"))
    with pytest.raises(ValueError, match="adopted"):
        OperationExecutionEvent.from_row(_event(effective_plan_role="baseline_best"))
    with pytest.raises(ValueError, match="scenario preview"):
        OperationExecutionEvent.from_row(_event(scenario_id="preview-1"))

    event = OperationExecutionEvent(
        id=1,
        schedule_version=2,
        schedule_id=100,
        op_id=10,
        batch_id="B1",
        event_type=EXECUTION_EVENT_START,
        reported_status="processing",
        event_time="2026-05-01 08:10:00",
        source_table="candidate_rows",
        effective_plan_role="adopted",
    )

    with pytest.raises(ValueError, match="current official"):
        build_operation_execution_state(
            op_id=10,
            batch_id="B1",
            events=[event],
            machine_resources={},
            operator_resources={},
        )
