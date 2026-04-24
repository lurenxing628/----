from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch, *, with_history: bool = True):
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
    if with_history:
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

    page_default = client.get("/scheduler/week-plan?week_start=2026-03-02")
    assert page_default.status_code == 200
    assert "版本：<strong>7</strong>" in page_default.get_data(as_text=True)

    page_latest = client.get("/scheduler/week-plan?week_start=2026-03-02&version=latest")
    assert page_latest.status_code == 200
    assert "版本：<strong>7</strong>" in page_latest.get_data(as_text=True)

    page_invalid = client.get("/scheduler/week-plan?week_start=2026-03-02&version=abc")
    assert page_invalid.status_code == 400
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in page_invalid.get_data(as_text=True)

    page_zero = client.get("/scheduler/week-plan?week_start=2026-03-02&version=0")
    assert page_zero.status_code == 400
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in page_zero.get_data(as_text=True)

    resp_default = client.get("/scheduler/week-plan/export?week_start=2026-03-02")
    assert resp_default.status_code == 200
    disposition_default = resp_default.headers.get("Content-Disposition", "")
    assert "v7_2026-03-02_to_2026-03-08.xlsx" in disposition_default, disposition_default

    resp_latest = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=latest")
    assert resp_latest.status_code == 200
    disposition_latest = resp_latest.headers.get("Content-Disposition", "")
    assert "v7_2026-03-02_to_2026-03-08.xlsx" in disposition_latest, disposition_latest

    resp_invalid = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=abc", follow_redirects=True)
    assert resp_invalid.status_code == 200
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in resp_invalid.get_data(as_text=True)

    resp_zero = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=0", follow_redirects=True)
    assert resp_zero.status_code == 200
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in resp_zero.get_data(as_text=True)


def test_week_plan_no_history_page_empty_and_export_404(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False)
    client = app.test_client()

    page_resp = client.get("/scheduler/week-plan?week_start=2026-03-02")
    page_html = page_resp.get_data(as_text=True)
    assert page_resp.status_code == 200
    assert "暂无版本" in page_html
    assert "版本：<strong>1</strong>" not in page_html
    assert "版本：<strong>0</strong>" not in page_html

    export_resp = client.get("/scheduler/week-plan/export?week_start=2026-03-02")
    assert export_resp.status_code == 404
    assert "暂无排产历史" in export_resp.get_data(as_text=True)
