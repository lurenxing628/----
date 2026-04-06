from __future__ import annotations

import importlib
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.services.equipment.machine_service import MachineService
from web.routes import equipment_pages as equipment_pages_mod

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _seed_machine(db_path: str, machine_id: str = "MC001") -> None:
    conn = get_connection(db_path)
    try:
        MachineService(conn).create(machine_id=machine_id, name="测试设备", status="active")
    finally:
        conn.close()


def test_equipment_page_shows_planned_downtime_when_overlay_available(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_machine(db_path)
    client = app.test_client()

    def _fake_list_active(self, now_str: str):
        return {"MC001"}

    monkeypatch.setattr(
        equipment_pages_mod.MachineDowntimeQueryService,
        "list_active_machine_ids_at",
        _fake_list_active,
    )

    resp = client.get("/equipment/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "停机（计划）" in body
    assert "计划停机状态读取失败" not in body


def test_equipment_page_marks_downtime_overlay_as_degraded_when_query_fails(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_machine(db_path)
    client = app.test_client()
    logged = []

    def _boom(self, now_str: str):
        raise RuntimeError("downtime query exploded")

    def _fake_exception(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(
        equipment_pages_mod.MachineDowntimeQueryService,
        "list_active_machine_ids_at",
        _boom,
    )
    monkeypatch.setattr(app.logger, "exception", _fake_exception)

    resp = client.get("/equipment/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "MC001" in body
    assert "计划停机状态读取失败，当前页面的“状态”列可能未展示“停机（计划）”覆盖状态，请查看日志并稍后刷新。" in body
    assert "Traceback" not in body
    assert any("设备列表页读取计划停机状态失败" in item for item in logged)
