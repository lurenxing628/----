from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.infrastructure.migration_state import detect_schema_is_current
from core.models.schedule_adjustment import DRAFT_STATUS_SAVED_SCENARIO
from core.services.scheduler.gantt_adjustment_draft_service import GanttAdjustmentDraftService
from core.services.scheduler.gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
from core.services.scheduler.gantt_service import GanttService
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from data.repositories import ScheduleAdjustmentRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 5


def _connect(tmp_path: Path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_names(conn) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def _index_names(conn) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {str(row["name"]) for row in rows}


def _snapshot(conn) -> dict:
    return {
        "schedule": [dict(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id").fetchall()],
        "history": [dict(row) for row in conn.execute("SELECT * FROM ScheduleHistory ORDER BY id").fetchall()],
        "seq": [dict(row) for row in conn.execute("SELECT * FROM ScheduleVersionSeq ORDER BY version").fetchall()],
        "candidate": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidate ORDER BY id").fetchall()],
        "candidate_rows": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateRows ORDER BY id").fetchall()],
        "candidate_selection": [
            dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateSelection ORDER BY id").fetchall()
        ],
    }


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


def _draft_with_change(
    conn,
    *,
    to_start: str = "2026-05-04 11:00:00",
    to_end: str = "2026-05-04 12:00:00",
    to_machine_id=None,
    to_operator_id=None,
) -> str:
    service = GanttAdjustmentDraftService(conn)
    draft = service.create_draft(base_version=VERSION, base_plan_role="adopted", created_by="pytest")
    service.record_time_change(draft_id=draft.draft_id, op_id=30, to_start=to_start, to_end=to_end)
    if to_machine_id is not None or to_operator_id is not None:
        service.record_resource_change(
            draft_id=draft.draft_id,
            op_id=30,
            to_machine_id=to_machine_id,
            to_operator_id=to_operator_id,
        )
    return draft.draft_id


def test_scenario_schema_exists_and_detection_requires_it(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"} <= _table_names(conn)
        assert {
            "idx_schedule_adjustment_scenario_base",
            "idx_schedule_adjustment_scenario_draft",
            "idx_schedule_adjustment_scenario_row_op",
            "idx_schedule_adjustment_scenario_row_time",
        } <= _index_names(conn)
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE ScheduleAdjustmentScenarioRow")
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_scenario_migration_preserves_existing_v12_data(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v12.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion (id, version) VALUES (1, 12);
            DROP TABLE ScheduleAdjustmentScenarioRow;
            DROP TABLE ScheduleAdjustmentScenario;
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            """
        )
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"} <= _table_names(conn)
        assert {
            "idx_schedule_adjustment_scenario_base",
            "idx_schedule_adjustment_scenario_draft",
            "idx_schedule_adjustment_scenario_row_op",
            "idx_schedule_adjustment_scenario_row_time",
        } <= _index_names(conn)
        assert detect_schema_is_current(conn)
        assert conn.execute("SELECT name FROM LegacyRows WHERE id=1").fetchone()["name"] == "keep-me"
    finally:
        conn.close()


def test_save_scenario_revalidates_and_does_not_touch_formal_tables(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_change(conn)
        before = _snapshot(conn)

        scenario = GanttAdjustmentScenarioService(conn).save_scenario(
            draft_id=draft_id,
            scenario_name="单日模拟",
            created_by="planner",
        )

        assert scenario.base_version == VERSION
        assert scenario.base_plan_role == "adopted"
        assert scenario.scenario_name == "单日模拟"
        assert scenario.validation_status == "valid"
        assert scenario.row_count == 3
        assert _snapshot(conn) == before
        draft = ScheduleAdjustmentRepository(conn).get_draft(draft_id)
        assert draft is not None
        assert draft.status == DRAFT_STATUS_SAVED_SCENARIO

        row = conn.execute(
            """
            SELECT start_time, end_time, is_changed
            FROM ScheduleAdjustmentScenarioRow
            WHERE scenario_id = ? AND op_id = 30
            """,
            (scenario.scenario_id,),
        ).fetchone()
        assert dict(row) == {
            "start_time": "2026-05-04 11:00:00",
            "end_time": "2026-05-04 12:00:00",
            "is_changed": "yes",
        }
    finally:
        conn.close()


def test_blocked_draft_cannot_save_scenario(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_change(
            conn,
            to_start="2026-05-04 10:30:00",
            to_end="2026-05-04 11:30:00",
            to_machine_id="M1",
            to_operator_id="O1",
        )
        before = _snapshot(conn)

        with pytest.raises(ValidationError, match="阻塞问题"):
            GanttAdjustmentScenarioService(conn).save_scenario(draft_id=draft_id)

        assert _snapshot(conn) == before
        assert conn.execute("SELECT COUNT(1) AS c FROM ScheduleAdjustmentScenario").fetchone()["c"] == 0
    finally:
        conn.close()


def test_scenario_id_preview_reads_scenario_rows_without_adopted_fallback(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = GanttAdjustmentScenarioService(conn).save_scenario(
            draft_id=_draft_with_change(conn),
            scenario_name="单日模拟",
        )
        plan_query = SchedulePlanQueryService(conn)

        formal_rows = plan_query.list_plan_detail_rows_between(
            version=VERSION,
            role="adopted",
            start_time="2026-05-04 00:00:00",
            end_time="2026-05-05 00:00:00",
        )
        scenario_rows = plan_query.list_plan_detail_rows_between_for_view(
            version=VERSION,
            role="adopted",
            scenario_id=scenario.scenario_id,
            start_time="2026-05-04 00:00:00",
            end_time="2026-05-05 00:00:00",
        )

        assert next(row for row in formal_rows if row["op_id"] == 30)["start_time"] == "2026-05-04 08:00:00"
        assert next(row for row in scenario_rows if row["op_id"] == 30)["start_time"] == "2026-05-04 11:00:00"
        with pytest.raises(ValueError, match="模拟方案不存在"):
            plan_query.resolve_plan_view(VERSION, "adopted", "scenario-missing")
    finally:
        conn.close()


def test_gantt_service_and_template_keep_scenario_preview_context(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = GanttAdjustmentScenarioService(conn).save_scenario(
            draft_id=_draft_with_change(conn),
            scenario_name="单日模拟",
        )
        data = GanttService(conn).get_gantt_tasks(
            view="machine",
            start_date="2026-05-04",
            end_date="2026-05-04",
            version=VERSION,
            plan_role="adopted",
            scenario_id=scenario.scenario_id,
        )
        op30_task = next(task for task in data["tasks"] if task["meta"]["op_id"] == 30)
        assert op30_task["start"] == "2026-05-04 11:00:00"
        assert data["is_scenario_preview"] is True
        assert data["scenario_id"] == scenario.scenario_id
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    response = client.get(
        f"/scheduler/gantt?version={VERSION}&plan_role=adopted&scenario_id={scenario.scenario_id}"
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "当前正在预览模拟方案" in html
    assert f'data-scenario-id="{scenario.scenario_id}"' in html
    assert f'name="scenario_id" value="{scenario.scenario_id}"' in html
    assert f"scenario_id={scenario.scenario_id}" in html
    zoom_html = client.get(
        f"/scheduler/gantt?version={VERSION}&plan_role=adopted&scenario_id={scenario.scenario_id}&gantt_zoom=hour"
    ).get_data(as_text=True)
    assert zoom_html.count("gantt_zoom=hour") >= 5
    assert "offset=-1" in zoom_html
    assert f"scenario_id={scenario.scenario_id}" in zoom_html


def test_save_scenario_route_uses_server_operator_not_json_created_by(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_change(conn)
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    response = client.post(
        "/scheduler/gantt/adjustments/save-scenario",
        json={
            "draft_id": draft_id,
            "scenario_name": "页面保存模拟",
            "created_by": "mallory",
            "base_version": VERSION,
            "base_plan_role": "adopted",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["created_by"] == "web"
    assert payload["data"]["scenario_name"] == "页面保存模拟"

    verify_conn = get_connection(str(tmp_path / "aps.db"))
    try:
        scenario = verify_conn.execute(
            "SELECT created_by FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
            (payload["data"]["scenario_id"],),
        ).fetchone()
        assert scenario["created_by"] == "web"
    finally:
        verify_conn.close()


def _build_app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "aps.db"
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "backups").mkdir(exist_ok=True)
    (tmp_path / "templates_excel").mkdir(exist_ok=True)

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    return importlib.import_module("app").create_app()
