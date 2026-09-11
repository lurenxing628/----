"""回归测试：报表页 /reports/overdue|utilization|downtime 默认选中最新排产版本（不暴露 v0），version=abc 返 400 用统一版本错误文案、version=999 返 404 提示版本不存在；日期范围需两侧齐全且格式合法否则 400；无排产历史时页面显示「暂无排产历史」且导出 404。"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from tests._support.excel_templates import point_env_at_shared
from tests._support.legacy_report_contract import (
    PageContract,
    assert_rejected,
    assert_retired,
    get_unchanged,
    saved_summary_display,
)
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch, *, with_history: bool = True):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

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


def _read(client, path):
    return get_unchanged(client, path, client.application.config["DATABASE_PATH"])


def _assert_missing_page(response):
    assert response.status_code == 404
    assert "Location" not in response.headers
    page = PageContract(response.get_data(as_text=True))
    assert "页面不存在或已被删除" in page.text
    assert "v0" not in page.text
    assert not page.controls
    assert not any("/export" in link or "version=" in link for link in page.links)


def test_reports_page_version_default_latest(tmp_path, monkeypatch) -> None:
    from core.services.scheduler.version_resolution import VERSION_ERROR_MESSAGE

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    for path, export_path in (
        ("/reports/overdue", "/reports/overdue/export?version=7&plan_role=adopted"),
        ("/reports/overdue?version=latest", "/reports/overdue/export?version=7&plan_role=adopted"),
        ("/reports/utilization", "/reports/utilization/export?version=7&plan_role=adopted"),
        ("/reports/downtime?version=latest", "/reports/downtime/export?version=7&plan_role=adopted"),
    ):
        assert_retired(_read(client, path), public=("7", "正式采用方案"), downloads=(export_path,))
    row, _display = saved_summary_display(app.config["DATABASE_PATH"], 7)
    assert row == ("simulated", '{"is_simulation": true, "completion_status": "partial"}')
    empty_export = _read(client, "/reports/overdue/export?version=7")
    assert empty_export.status_code == 400
    assert "当前版本没有可导出的超期结果，请换一个排产版本后再试。" in empty_export.get_data(as_text=True)

    invalid_resp = _read(client, "/reports/overdue?version=abc")
    assert_rejected(invalid_resp, forbidden=("version 不合法", "abc"))
    invalid_export = _read(client, "/reports/overdue/export?version=abc")
    assert invalid_export.status_code == 400
    assert VERSION_ERROR_MESSAGE in invalid_export.get_data(as_text=True)

    _assert_missing_page(_read(client, "/reports/overdue?version=999"))
    missing_export = _read(client, "/reports/overdue/export?version=999")
    assert missing_export.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in missing_export.get_data(as_text=True)


def test_reports_page_date_range_requires_both_sides_and_valid_format(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    cases = (
        ("start_date=2026-01-01", "缺少开始日期或结束日期"),
        ("end_date=2026-01-07", "缺少开始日期或结束日期"),
        ("start_date=bad-date&end_date=2026-01-07", "日期格式不正确"),
        ("start_date=2026-01-01&end_date=bad-date", "日期格式不正确"),
        ("start_date=2026-01-01&end_date=2026-04-15", "日期范围不能超过 62 天"),
    )
    for endpoint in ("/reports/utilization", "/reports/downtime"):
        for query, message in cases:
            assert_rejected(_read(client, f"{endpoint}?version=latest&{query}"))
            exported = _read(client, f"{endpoint}/export?version=latest&{query}")
            assert exported.status_code == 400
            assert message in exported.get_data(as_text=True)

        dates = "start_date=2026-01-01&end_date=2026-01-07"
        assert_retired(
            _read(client, f"{endpoint}?version=latest&{dates}"),
            public=("7", "正式采用方案", "2026-01-01 至 2026-01-07"),
            downloads=(f"{endpoint}/export?version=7&{dates}&plan_role=adopted",),
        )
        empty_export = _read(client, f"{endpoint}/export?version=latest&{dates}")
        assert empty_export.status_code == 400
        assert "暂无数据，不能导出" in empty_export.get_data(as_text=True)


def test_reports_no_history_pages_do_not_expose_v0_and_exports_404(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False)
    client = app.test_client()

    _assert_missing_page(_read(client, "/reports/overdue"))
    export_resp = _read(client, "/reports/overdue/export")
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
