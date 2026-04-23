from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (7, "greedy", 0, 0, "success", "{}", "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_week_plan_filename_uses_normalized_version(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_invalid = client.get("/scheduler/week-plan?week_start=2026-03-02&version=abc")
    assert page_invalid.status_code == 200
    assert "版本：<strong>7</strong>" in page_invalid.get_data(as_text=True)

    page_zero = client.get("/scheduler/week-plan?week_start=2026-03-02&version=0")
    assert page_zero.status_code == 200
    assert "版本：<strong>7</strong>" in page_zero.get_data(as_text=True)

    resp_invalid = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=abc")
    assert resp_invalid.status_code == 200
    disposition_invalid = resp_invalid.headers.get("Content-Disposition", "")
    assert "v7_2026-03-02_to_2026-03-08.xlsx" in disposition_invalid, disposition_invalid

    resp = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=0")
    assert resp.status_code == 200
    disposition = resp.headers.get("Content-Disposition", "")
    assert "v7_2026-03-02_to_2026-03-08.xlsx" in disposition, disposition
