"""旧列表明确退役、不再执行查询；保留停机读模型、降级原因、日志及原设备下载。"""

from __future__ import annotations

import importlib
from pathlib import Path

from flask import g

from core.infrastructure.database import ensure_schema, get_connection
from core.services.equipment.machine_service import MachineService
from tests._support.excel_templates import point_env_at_shared
from tests._support.legacy_http import assert_retired_response, xlsx_download_rows
from tests._support.paths import REPO_ROOT
from tests._support.sqlite_snapshot import table_rows
from web.routes import equipment_pages as equipment_pages_mod

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _seed_machine(db_path: str, machine_id: str = "MC001") -> None:
    conn = get_connection(db_path)
    try:
        MachineService(conn).create(machine_id=machine_id, name="测试设备", status="active")
    finally:
        conn.close()


def _read_overlay_model(app, db_path):
    """Check existing read-model components, never invoke or render the retired handler."""
    conn = get_connection(db_path)
    try:
        before = {table: table_rows(conn, table) for table in ("Machines", "MachineDowntimes")}
        changes = conn.total_changes
        with app.app_context():
            g.db = conn
            state = equipment_pages_mod._load_active_downtime_machine_ids()
            rows = equipment_pages_mod._build_machine_list_rows(
                MachineService(conn).list(), op_types={}, team_name_map={}, links_by_machine={},
                downtime_now_set=state["machine_ids"],
            )
            assert before == {table: table_rows(conn, table) for table in before}
            assert conn.total_changes == changes
        return state, rows
    finally:
        conn.close()


def test_equipment_page_shows_planned_downtime_when_overlay_available(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_machine(db_path)
    client = app.test_client()
    calls = []

    def _fake_list_active(self, now_str: str):
        calls.append(now_str)
        return {"MC001"}

    monkeypatch.setattr(
        equipment_pages_mod.MachineDowntimeQueryService,
        "list_active_machine_ids_at",
        _fake_list_active,
    )

    body = assert_retired_response(client.get("/equipment/"))
    assert not calls and "计划停机状态读取失败" not in body
    state, rows = _read_overlay_model(app, db_path)
    assert len(calls) == 1
    assert state == {"machine_ids": {"MC001"}, "degraded": False, "reason": None}
    assert len(rows) == 1 and rows[0]["machine_id"] == "MC001"
    assert rows[0]["status"] == "active" and rows[0]["status_zh"] == "停机（计划）"
    exported = xlsx_download_rows(client.get("/equipment/excel/machines/export"))
    assert len(exported) == 1 and exported[0]["设备编号"] == "MC001"


def test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_machine(db_path)
    client = app.test_client()
    logged = []
    calls = []

    def _boom(self, now_str: str):
        calls.append(now_str)
        raise RuntimeError("downtime query exploded")

    def _fake_exception(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(
        equipment_pages_mod.MachineDowntimeQueryService,
        "list_active_machine_ids_at",
        _boom,
    )
    monkeypatch.setattr(app.logger, "exception", _fake_exception)

    body = assert_retired_response(client.get("/equipment/"))
    assert not calls and not logged
    state, rows = _read_overlay_model(app, db_path)
    assert len(calls) == 1
    assert state == {"machine_ids": set(), "degraded": True, "reason": "query_failed"}
    assert len(rows) == 1 and rows[0]["machine_id"] == "MC001"
    assert rows[0]["status"] == "active" and rows[0]["status_zh"] != "停机（计划）"
    assert "Traceback" not in body and "downtime query exploded" not in body
    assert any("设备列表页读取计划停机状态失败" in item for item in logged)
    exported = xlsx_download_rows(client.get("/equipment/excel/machines/export"))
    assert len(exported) == 1 and exported[0]["设备编号"] == "MC001"
