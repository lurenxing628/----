from __future__ import annotations

import importlib
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection

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



def _insert_history(db_path: str, *, version: int, result_summary: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version, "priority_first", 0, 0, "success", result_summary, "pytest"),
        )
        conn.commit()
    finally:
        conn.close()



def _capture_warning_logs(app, monkeypatch):
    logged = []

    def _fake_warning(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    return logged



def test_dashboard_logs_warning_when_latest_result_summary_is_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=1, result_summary="{invalid json")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/")

    assert resp.status_code == 200
    assert any("首页 result_summary 解析失败（version=1" in item for item in warnings)



def test_scheduler_batches_keeps_latest_history_when_summary_is_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=2, result_summary="{invalid json")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/scheduler/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "版本：<strong>v2</strong>" in body
    assert "还没有排过产" not in body
    assert any("排产页 result_summary 解析失败（version=2" in item for item in warnings)



def test_system_history_logs_warning_for_selected_and_list_summary_parse_failures(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=3, result_summary="{selected broken")
    _insert_history(db_path, version=4, result_summary="{list broken")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/system/history?version=3")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "版本详情：v3" in body
    assert "最近排产记录" in body
    assert any("排产历史页 result_summary 解析失败（version=3, source=selected" in item for item in warnings)
    assert any("排产历史页 result_summary 解析失败（version=4, source=list" in item for item in warnings)
