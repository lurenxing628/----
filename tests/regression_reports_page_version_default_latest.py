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
            (
                7,
                "greedy",
                0,
                0,
                "simulated",
                '{"is_simulation": true, "completion_status": "partial"}',
                "pytest",
            ),
        )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _assert_selected_latest(html: str, version: int) -> None:
    assert f'value="{version}" selected' in html, html


def test_reports_page_version_default_latest(tmp_path, monkeypatch) -> None:
    from core.services.scheduler.version_resolution import VERSION_ERROR_MESSAGE

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    overdue_html = client.get("/reports/overdue").get_data(as_text=True)
    _assert_selected_latest(overdue_html, 7)
    assert "v7 · 部分成功" in overdue_html
    assert "模拟排产）" not in overdue_html
    assert "aps-disabled-button" in overdue_html
    assert "当前版本没有可导出的超期结果，请换一个排产版本后再试。" in overdue_html

    overdue_latest_html = client.get("/reports/overdue?version=latest").get_data(as_text=True)
    _assert_selected_latest(overdue_latest_html, 7)

    utilization_html = client.get("/reports/utilization").get_data(as_text=True)
    _assert_selected_latest(utilization_html, 7)
    assert "v7 · 部分成功" in utilization_html
    assert "aps-disabled-button" in utilization_html

    downtime_html = client.get("/reports/downtime?version=latest").get_data(as_text=True)
    _assert_selected_latest(downtime_html, 7)
    assert "v7 · 部分成功" in downtime_html
    assert "aps-disabled-button" in downtime_html

    invalid_resp = client.get("/reports/overdue?version=abc")
    invalid_html = invalid_resp.get_data(as_text=True)
    assert invalid_resp.status_code == 400
    assert VERSION_ERROR_MESSAGE in invalid_html
    assert "version 不合法" not in invalid_html

    missing_resp = client.get("/reports/overdue?version=999")
    missing_html = missing_resp.get_data(as_text=True)
    assert missing_resp.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in missing_html


def test_reports_no_history_pages_do_not_expose_v0_and_exports_404(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False)
    client = app.test_client()

    overdue_resp = client.get("/reports/overdue")
    overdue_html = overdue_resp.get_data(as_text=True)
    assert overdue_resp.status_code == 200
    assert "暂无排产历史" in overdue_html
    assert "v0" not in overdue_html

    export_resp = client.get("/reports/overdue/export")
    assert export_resp.status_code == 404
    assert "暂无排产历史" in export_resp.get_data(as_text=True)


def test_reports_export_explicit_missing_version_uses_missing_version_message(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    export_resp = client.get("/reports/overdue/export?version=999")
    body = export_resp.get_data(as_text=True)

    assert export_resp.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in body
    assert "暂无排产历史，无法导出报表。" not in body
