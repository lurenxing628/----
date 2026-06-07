"""回归测试：GanttAdjustmentPublishService.publish_scenario 正式采用调整方案——v13 迁移补齐 published_* 列且按列缺失判定 schema 不达标，发布生成新正式版本并写审计日志/路由用服务端 operator(web)，且拒绝对比方案、操作日志失败回滚、缺确认语/原因、重复采用、陈旧依据版本与发布前需重校验等场景，失败时不留任何正式写入。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set

import pytest
from regression_gantt_draft_save_and_preview import _build_app

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.errors import AppError, ValidationError
from core.infrastructure.logging import OperationLogger
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v13 import _ADJUSTMENT_SCENARIO_SQL
from core.models.schedule_adjustment import DRAFT_STATUS_PUBLISHED, SCENARIO_STATUS_PUBLISHED
from core.services.scheduler.gantt_adjustment_draft_service import GanttAdjustmentDraftService
from core.services.scheduler.gantt_adjustment_publish_service import GanttAdjustmentPublishService
from core.services.scheduler.gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 5
PUBLISH_COLUMNS = {
    "published_version": "INTEGER",
    "published_by": "TEXT",
    "published_reason": "TEXT",
    "published_at": "DATETIME",
}


def _connect(tmp_path: Path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_columns(conn, table: str) -> Set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _snapshot_formal(conn) -> dict:
    return {
        "schedule": [dict(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id").fetchall()],
        "history": [dict(row) for row in conn.execute("SELECT * FROM ScheduleHistory ORDER BY id").fetchall()],
        "seq": [dict(row) for row in conn.execute("SELECT * FROM ScheduleVersionSeq ORDER BY version").fetchall()],
    }


def _recreate_scenario_without_column(conn, missing_column: str) -> None:
    conn.executescript(
        """
        DROP TABLE ScheduleAdjustmentScenarioRow;
        DROP TABLE ScheduleAdjustmentScenario;
        """
    )
    conn.executescript(_ADJUSTMENT_SCENARIO_SQL)
    for column_name, column_type in PUBLISH_COLUMNS.items():
        if column_name != missing_column:
            conn.execute(f"ALTER TABLE ScheduleAdjustmentScenario ADD COLUMN {column_name} {column_type}")
    conn.commit()


def _seed_base(conn) -> None:
    conn.executescript(
        f"""
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '设备一', 'active'), ('M2', '设备二', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '人员一', 'active'), ('O2', '人员二', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一'), ('P002', '零件二');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES
          ('B1', 'P001', '零件一', 1, '2026-05-20', 'normal', 'yes', 'scheduled'),
          ('B2', 'P002', '零件二', 1, '2026-05-20', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES
          (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled'),
          (20, 'OP20', 'B1', 'piece-a', 20, '钻孔', 'internal', 'scheduled'),
          (30, 'OP30', 'B2', 'piece-b', 10, '铣削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES ({VERSION});

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
          (70, 10, 'M1', 'O1', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION}),
          (80, 20, 'M1', 'O1', '2026-05-04 10:00:00', '2026-05-04 11:00:00', 'unlocked', {VERSION}),
          (90, 30, 'M2', 'O2', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION});

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES ({VERSION}, 'priority_first', 2, 3, 'success', '{{}}', 'pytest');
        """
    )
    conn.commit()


def _saved_scenario(conn):
    draft_service = GanttAdjustmentDraftService(conn)
    draft = draft_service.create_draft(base_version=VERSION, base_plan_role="adopted", created_by="pytest")
    draft_service.record_time_change(
        draft_id=draft.draft_id,
        op_id=30,
        to_start="2026-05-04 11:00:00",
        to_end="2026-05-04 12:00:00",
    )
    return GanttAdjustmentScenarioService(conn).save_scenario(
        draft_id=draft.draft_id,
        scenario_name="单日模拟",
        created_by="planner",
    )


def _seed_baseline_best_selection(conn) -> None:
    conn.execute(
        """
        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES (?, 'adopted', '正式采用', 'baseline', 'completed', 'no', 'no')
        """,
        (VERSION,),
    )
    adopted_candidate_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES (?, 'baseline_best', '原算法代表方案', 'baseline', 'completed', 'no', 'yes')
        """,
        (VERSION,),
    )
    baseline_candidate_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (?, 'adopted', ?, 'schedule')
        """,
        (VERSION, adopted_candidate_id),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (?, 'baseline_best', ?, 'candidate_rows')
        """,
        (VERSION, baseline_candidate_id),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status)
        SELECT version, ?, op_id, machine_id, operator_id, start_time, end_time, lock_status
          FROM Schedule
         WHERE version = ?
        """,
        (baseline_candidate_id, VERSION),
    )
    conn.commit()


def _saved_baseline_best_scenario(conn):
    _seed_baseline_best_selection(conn)
    draft_service = GanttAdjustmentDraftService(conn)
    draft = draft_service.create_draft(base_version=VERSION, base_plan_role="baseline_best", created_by="pytest")
    draft_service.record_time_change(
        draft_id=draft.draft_id,
        op_id=30,
        to_start="2026-05-04 11:00:00",
        to_end="2026-05-04 12:00:00",
    )
    return GanttAdjustmentScenarioService(conn).save_scenario(
        draft_id=draft.draft_id,
        scenario_name="对比方案模拟",
        created_by="planner",
        expected_base_version=VERSION,
        expected_base_plan_role="baseline_best",
    )


def test_publish_schema_columns_exist_and_v13_migrates(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {"published_version", "published_by", "published_reason", "published_at"} <= _table_columns(
            conn, "ScheduleAdjustmentScenario"
        )
        assert detect_schema_is_current(conn)
    finally:
        conn.close()

    db_path = tmp_path / "legacy_v13.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion(id, version) VALUES (1, 13);
            DROP TABLE ScheduleAdjustmentScenarioRow;
            DROP TABLE ScheduleAdjustmentScenario;
            """
        )
        conn.executescript(_ADJUSTMENT_SCENARIO_SQL)
        conn.commit()
        assert "published_version" not in _table_columns(conn, "ScheduleAdjustmentScenario")
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {"published_version", "published_by", "published_reason", "published_at"} <= _table_columns(
            conn, "ScheduleAdjustmentScenario"
        )
        assert detect_schema_is_current(conn)
    finally:
        conn.close()


def test_schema_detection_requires_every_publish_column(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        for column_name in PUBLISH_COLUMNS:
            _recreate_scenario_without_column(conn, column_name)
            assert not detect_schema_is_current(conn), column_name
    finally:
        conn.close()


def test_publish_scenario_creates_new_formal_version_and_audit_log(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        before_v5 = [dict(row) for row in conn.execute("SELECT * FROM Schedule WHERE version=? ORDER BY id", (VERSION,))]

        result = GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
            scenario_id=scenario.scenario_id,
            confirm_text="正式采用",
            reason="客户交期确认后采用",
            published_by="planner",
            expected_base_version=VERSION,
            expected_base_plan_role="adopted",
        )

        assert result.new_version == VERSION + 1
        assert [dict(row) for row in conn.execute("SELECT * FROM Schedule WHERE version=? ORDER BY id", (VERSION,))] == before_v5
        new_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT op_id, machine_id, operator_id, start_time, end_time, lock_status, version FROM Schedule WHERE version=? ORDER BY op_id",
                (result.new_version,),
            )
        ]
        assert len(new_rows) == 3
        assert next(row for row in new_rows if row["op_id"] == 30)["start_time"] == "2026-05-04 11:00:00"

        history = conn.execute("SELECT * FROM ScheduleHistory WHERE version=?", (result.new_version,)).fetchone()
        assert history["strategy"] == "manual"
        assert history["batch_count"] == 2
        assert history["op_count"] == 3
        summary = json.loads(history["result_summary"])
        assert summary["source"] == "gantt_scenario_publish"
        assert summary["scenario_id"] == scenario.scenario_id
        assert summary["reason"] == "客户交期确认后采用"

        scenario_row = conn.execute("SELECT * FROM ScheduleAdjustmentScenario WHERE scenario_id=?", (scenario.scenario_id,)).fetchone()
        assert scenario_row["status"] == SCENARIO_STATUS_PUBLISHED
        assert scenario_row["published_version"] == result.new_version
        assert scenario_row["published_by"] == "planner"
        assert scenario_row["published_reason"] == "客户交期确认后采用"

        draft_row = conn.execute("SELECT status, reason FROM ScheduleAdjustmentDraft WHERE draft_id=?", (scenario.source_draft_id,)).fetchone()
        assert dict(draft_row) == {"status": DRAFT_STATUS_PUBLISHED, "reason": "客户交期确认后采用"}

        log = conn.execute("SELECT * FROM OperationLogs WHERE action='publish_scenario'").fetchone()
        assert log["target_id"] == str(result.new_version)
        assert log["operator"] == "planner"
        assert json.loads(log["detail"])["scenario_id"] == scenario.scenario_id
    finally:
        conn.close()


def test_publish_rejects_scenario_based_on_comparison_plan(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_baseline_best_scenario(conn)
        before = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="正式采用方案"):
            GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
                published_by="planner",
                expected_base_version=VERSION,
                expected_base_plan_role="baseline_best",
            )

        assert _snapshot_formal(conn) == before
        scenario_row = conn.execute(
            """
            SELECT status, published_version, published_by, published_reason, published_at
            FROM ScheduleAdjustmentScenario
            WHERE scenario_id=?
            """,
            (scenario.scenario_id,),
        ).fetchone()
        assert dict(scenario_row) == {
            "status": "active",
            "published_version": None,
            "published_by": None,
            "published_reason": None,
            "published_at": None,
        }
    finally:
        conn.close()


def test_publish_scenario_route_uses_server_operator_not_system_or_json(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    response = client.post(
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
    assert payload["data"]["published_by"] == "web"
    assert payload["data"]["published_by"] != "system"

    verify_conn = get_connection(str(tmp_path / "aps.db"))
    try:
        scenario_row = verify_conn.execute(
            "SELECT published_by, published_reason FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
            (scenario.scenario_id,),
        ).fetchone()
        assert dict(scenario_row) == {"published_by": "web", "published_reason": "页面确认采用"}
        history_row = verify_conn.execute(
            "SELECT created_by FROM ScheduleHistory WHERE version = ?",
            (VERSION + 1,),
        ).fetchone()
        assert history_row["created_by"] == "web"
        log_row = verify_conn.execute("SELECT operator FROM OperationLogs WHERE action = 'publish_scenario'").fetchone()
        assert log_row["operator"] == "web"
    finally:
        verify_conn.close()


def test_publish_requires_operation_log_success_and_rolls_back(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        before = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="操作日志"):
            GanttAdjustmentPublishService(conn).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
            )

        assert _snapshot_formal(conn) == before
        row = conn.execute("SELECT status, published_version FROM ScheduleAdjustmentScenario WHERE scenario_id=?", (scenario.scenario_id,)).fetchone()
        assert dict(row) == {"status": "active", "published_version": None}
    finally:
        conn.close()


def test_publish_operation_log_failure_is_visible_and_rolls_back(tmp_path: Path) -> None:
    class _FailingOperationLogger:
        def __init__(self):
            self.kwargs = None

        def info(self, **kwargs):
            self.kwargs = kwargs
            return False

    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        before = _snapshot_formal(conn)
        op_logger = _FailingOperationLogger()

        with pytest.raises(AppError, match="操作日志写入失败"):
            GanttAdjustmentPublishService(conn, op_logger=op_logger).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
            )

        assert op_logger.kwargs["raise_on_fail"] is True
        assert _snapshot_formal(conn) == before
    finally:
        conn.close()


def test_publish_rejects_reused_scenario_without_second_formal_version(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        service = GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn))
        first = service.publish_scenario(
            scenario_id=scenario.scenario_id,
            confirm_text="正式采用",
            reason="第一次采用",
            published_by="planner",
        )
        before_second = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="可预览"):
            service.publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="第二次采用",
                published_by="planner",
            )

        assert _snapshot_formal(conn) == before_second
        assert conn.execute("SELECT COUNT(1) AS c FROM ScheduleHistory WHERE version > ?", (VERSION,)).fetchone()["c"] == 1
        assert first.new_version == VERSION + 1
    finally:
        conn.close()


def test_publish_claim_rejects_inconsistent_already_claimed_scenario(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        conn.execute(
            "UPDATE ScheduleAdjustmentScenario SET published_version = 99 WHERE scenario_id = ?",
            (scenario.scenario_id,),
        )
        conn.commit()
        before = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="已经被采用"):
            GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
            )

        assert _snapshot_formal(conn) == before
    finally:
        conn.close()


def test_publish_requires_confirm_text_and_reason_without_formal_writes(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        before = _snapshot_formal(conn)
        service = GanttAdjustmentPublishService(conn)

        with pytest.raises(ValidationError, match="正式采用"):
            service.publish_scenario(scenario_id=scenario.scenario_id, confirm_text="确认", reason="客户要求")
        with pytest.raises(ValidationError, match="不能为空"):
            service.publish_scenario(scenario_id=scenario.scenario_id, confirm_text="正式采用", reason=" ")

        assert _snapshot_formal(conn) == before
    finally:
        conn.close()


def test_publish_rejects_stale_base_version(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (?)", (VERSION + 1,))
        conn.execute(
            """
            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, 'priority_first', 0, 0, 'success', '{}', 'other')
            """,
            (VERSION + 1,),
        )
        conn.commit()
        before = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="调整依据版本"):
            GanttAdjustmentPublishService(conn).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
                published_by="planner",
            )

        assert _snapshot_formal(conn) == before
    finally:
        conn.close()


def test_publish_revalidates_saved_draft_before_writing(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = _saved_scenario(conn)
        conn.execute(
            """
            INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
            VALUES ('M2', '2026-05-04 10:30:00', '2026-05-04 12:30:00', 'active')
            """
        )
        conn.commit()
        before = _snapshot_formal(conn)

        with pytest.raises(ValidationError, match="重新校验"):
            GanttAdjustmentPublishService(conn).publish_scenario(
                scenario_id=scenario.scenario_id,
                confirm_text="正式采用",
                reason="客户要求",
                published_by="planner",
            )

        assert _snapshot_formal(conn) == before
    finally:
        conn.close()
