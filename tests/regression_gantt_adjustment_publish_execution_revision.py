from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from regression_gantt_draft_save_and_preview import _build_app
from regression_gantt_scenario_publish import (
    SCHEMA_PATH,
    VERSION,
    _connect,
    _saved_scenario,
    _seed_base,
    _snapshot_formal,
)

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.errors import AppError
from core.infrastructure.logging import OperationLogger
from core.infrastructure.migration_state import detect_schema_is_current
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.gantt_adjustment_draft_service import GanttAdjustmentDraftService
from core.services.scheduler.gantt_adjustment_publish_service import GanttAdjustmentPublishService
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)


def _snapshot_columns(conn: sqlite3.Connection) -> set:
    return {str(row["name"]) for row in conn.execute("PRAGMA table_info(ScheduleAdjustmentScenario)").fetchall()}


def _event_context(*, revision: str = "10:0:0") -> ExecutionFeedbackContext:
    return ExecutionFeedbackContext(
        schedule_version=VERSION,
        schedule_id=70,
        op_id=10,
        batch_id="B1",
        expected_state_revision=revision,
        created_by="planner",
        idempotency_key="scenario-start-key",
        requested_plan_role=ROLE_ADOPTED,
        source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED,
        scenario_id=None,
    )


def _scenario_snapshot(conn: sqlite3.Connection, scenario_id: str):
    row = conn.execute(
        """
        SELECT execution_snapshot_revision, execution_snapshot_op_ids, execution_snapshot_op_count
        FROM ScheduleAdjustmentScenario
        WHERE scenario_id = ?
        """,
        (scenario_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


def _scenario_publish_fields(conn: sqlite3.Connection, scenario_id: str):
    row = conn.execute(
        """
        SELECT status, published_version, published_by, published_reason, published_at
        FROM ScheduleAdjustmentScenario
        WHERE scenario_id = ?
        """,
        (scenario_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


def _assert_no_internal_scenario_fields(data: dict) -> None:
    forbidden = {
        "scenario_id",
        "source_draft_id",
        "base_version",
        "base_plan_role",
        "base_source_table",
        "base_candidate_id",
        "base_candidate_key",
        "status",
        "validation_status",
        "issue_count",
        "issues_json",
        "row_count",
        "execution_snapshot_revision",
        "execution_snapshot_op_ids",
        "execution_snapshot_op_count",
    }
    assert forbidden.isdisjoint(data.keys())


def test_v17_schema_and_migration_add_scenario_execution_snapshot_columns(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {
            "execution_snapshot_revision",
            "execution_snapshot_op_ids",
            "execution_snapshot_op_count",
        } <= _snapshot_columns(conn)
        assert detect_schema_is_current(conn)
    finally:
        conn.close()

    db_path = tmp_path / "legacy_v16_without_snapshot.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion(id, version) VALUES (1, 16);
            DROP TABLE ScheduleAdjustmentScenarioRow;
            DROP TABLE ScheduleAdjustmentScenario;
            CREATE TABLE ScheduleAdjustmentScenario (
                scenario_id        TEXT PRIMARY KEY,
                source_draft_id    TEXT NOT NULL UNIQUE,
                base_version       INTEGER NOT NULL,
                base_plan_role     TEXT NOT NULL CHECK(base_plan_role IN ('adopted', 'baseline_best', 'critical_best')),
                base_source_table  TEXT NOT NULL,
                base_candidate_id  INTEGER,
                base_candidate_key TEXT,
                scenario_name      TEXT,
                status             TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'discarded', 'published', 'expired')),
                validation_status  TEXT NOT NULL CHECK(validation_status IN ('valid', 'warning')),
                issue_count        INTEGER NOT NULL DEFAULT 0,
                issues_json        TEXT,
                row_count          INTEGER NOT NULL DEFAULT 0,
                created_by         TEXT,
                published_version  INTEGER,
                published_by       TEXT,
                published_reason   TEXT,
                published_at       DATETIME,
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE ScheduleAdjustmentScenarioRow (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id         TEXT NOT NULL,
                source_table        TEXT NOT NULL,
                source_row_id       INTEGER,
                op_id               INTEGER NOT NULL,
                machine_id          TEXT,
                operator_id         TEXT,
                start_time          DATETIME NOT NULL,
                end_time            DATETIME NOT NULL,
                lock_status         TEXT,
                is_changed          TEXT NOT NULL DEFAULT 'no' CHECK(is_changed IN ('yes', 'no')),
                change_summary_json TEXT,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_schedule_adjustment_scenario_base
            ON ScheduleAdjustmentScenario(base_version, base_plan_role, status);
            CREATE INDEX idx_schedule_adjustment_scenario_draft
            ON ScheduleAdjustmentScenario(source_draft_id);
            CREATE UNIQUE INDEX idx_schedule_adjustment_scenario_row_op
            ON ScheduleAdjustmentScenarioRow(scenario_id, op_id);
            CREATE INDEX idx_schedule_adjustment_scenario_row_time
            ON ScheduleAdjustmentScenarioRow(scenario_id, start_time, end_time);
            """
        )
        conn.commit()
        assert "execution_snapshot_revision" not in _snapshot_columns(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {
            "execution_snapshot_revision",
            "execution_snapshot_op_ids",
            "execution_snapshot_op_count",
        } <= _snapshot_columns(conn)
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def test_save_scenario_records_execution_snapshot_without_formal_writes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        before = _snapshot_formal(conn)
        scenario = _saved_scenario(conn)

        snapshot = _scenario_snapshot(conn, scenario.scenario_id)
        assert snapshot["execution_snapshot_revision"].startswith("execution-snapshot:")
        assert json.loads(snapshot["execution_snapshot_op_ids"]) == [10, 20, 30]
        assert snapshot["execution_snapshot_op_count"] == 3
        assert _snapshot_formal(conn) == before
    finally:
        conn.close()


def test_publish_rechecks_saved_snapshot_and_rolls_back_when_shop_floor_changes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        OperationExecutionFeedbackService(conn).start_operation(
            _event_context(),
            event_time="2026-05-04 08:30:00",
            operator_id="O1",
            machine_id="M1",
        )
        before_formal = _snapshot_formal(conn)

        with pytest.raises(AppError) as exc_info:
            GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户确认",
                published_by="planner",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_snapshot_changed"
        assert "现场状态刚刚变了" in exc_info.value.message
        assert _snapshot_formal(conn) == before_formal
        assert _scenario_publish_fields(conn, scenario.scenario_id) == {
            "status": "active",
            "published_version": None,
            "published_by": None,
            "published_reason": None,
            "published_at": None,
        }
        assert conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE action='publish_scenario'").fetchone()[0] == 0
    finally:
        conn.close()


def test_publish_rejects_saved_scenario_that_moves_started_operation_without_formal_writes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        OperationExecutionFeedbackService(conn).start_operation(
            _event_context(),
            event_time="2026-05-04 08:30:00",
            operator_id="O1",
            machine_id="M1",
        )
        scenario = _saved_scenario(conn)
        before_formal = _snapshot_formal(conn)

        with pytest.raises(AppError) as exc_info:
            GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户确认",
                published_by="planner",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_fixed_start_moved"
        assert exc_info.value.details["op_id"] == 10
        assert "不能改掉实际开工时间" in exc_info.value.message
        assert _snapshot_formal(conn) == before_formal
        assert _scenario_publish_fields(conn, scenario.scenario_id) == {
            "status": "active",
            "published_version": None,
            "published_by": None,
            "published_reason": None,
            "published_at": None,
        }
        assert conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE action='publish_scenario'").fetchone()[0] == 0
    finally:
        conn.close()


def test_publish_writes_execution_snapshot_to_history_summary(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        result = GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
            scenario_id=scenario.scenario_id,
            confirm_text="正式采用",
            reason="客户确认",
            published_by="planner",
        )

        history = conn.execute(
            "SELECT result_summary FROM ScheduleHistory WHERE version = ?",
            (result.new_version,),
        ).fetchone()
        summary = json.loads(history["result_summary"])
        snapshot = summary["execution_snapshot"]
        assert snapshot["execution_snapshot_revision"].startswith("execution-snapshot:")
        assert snapshot["execution_snapshot_op_ids"] == [10, 20, 30]
        assert snapshot["execution_snapshot_op_count"] == 3
    finally:
        conn.close()


def test_save_scenario_route_does_not_expose_internal_scenario_fields(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_service = GanttAdjustmentDraftService(conn)
        draft = draft_service.create_draft(base_version=VERSION, base_plan_role="adopted", created_by="pytest")
        draft_service.record_time_change(
            draft_id=draft.draft_id,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
        )
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    response = app.test_client().post(
        "/scheduler/gantt/adjustments/save-scenario",
        json={
            "draft_id": draft.draft_id,
            "scenario_name": "页面保存模拟",
            "base_version": VERSION,
            "base_plan_role": "adopted",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    data = payload["data"]
    assert data["scenario_name"] == "页面保存模拟"
    assert data["created_by"] == "web"
    assert data["preview_url"]
    assert data["message"] == "已保存为模拟方案，正式计划还没有改变。"
    _assert_no_internal_scenario_fields(data)


def test_publish_scenario_route_does_not_expose_internal_scenario_fields(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    response = app.test_client().post(
        "/scheduler/gantt/adjustments/publish-scenario",
        json={
            "scenario_id": scenario.scenario_id,
            "confirm_text": "正式采用",
            "reason": "页面确认采用",
            "published_by": "mallory",
            "base_version": VERSION,
            "base_plan_role": "adopted",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    data = payload["data"]
    assert data["new_version"] == VERSION + 1
    assert data["published_by"] == "web"
    assert data["reason"] == "页面确认采用"
    assert data["view_url"]
    assert data["message"] == "已正式采用模拟方案，并生成新的正式排产版本。"
    _assert_no_internal_scenario_fields(data)
