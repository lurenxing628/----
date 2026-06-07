"""回归测试：/scheduler/week-plan 周计划页与导出——version 缺省/latest 都规范化为最新版 v7（导出文件名为 v7_起至.xlsx），非法 version（abc/0）返回 400 中文提示；无历史时页面显示「暂无版本」、导出 404；导出仅按 week_start 取数（忽略陈旧 start/end_date 范围），导出失败重定向回 week-plan 并保留 week_start/offset/version/plan_role 上下文。"""

from __future__ import annotations

import importlib
import io
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import openpyxl

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

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_week_plan_filename_uses_normalized_version(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_default = client.get("/scheduler/week-plan?week_start=2026-03-02")
    assert page_default.status_code == 200

    page_latest = client.get("/scheduler/week-plan?week_start=2026-03-02&version=latest")
    assert page_latest.status_code == 200

    page_invalid = client.get("/scheduler/week-plan?week_start=2026-03-02&version=abc")
    assert page_invalid.status_code == 400
    assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in page_invalid.get_data(as_text=True)

    page_zero = client.get("/scheduler/week-plan?week_start=2026-03-02&version=0")
    assert page_zero.status_code == 400
    assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in page_zero.get_data(as_text=True)

    resp_default = client.get("/scheduler/week-plan/export?week_start=2026-03-02")
    assert resp_default.status_code == 200
    disposition_default = unquote(resp_default.headers.get("Content-Disposition", ""))
    assert "v7_2026-03-02至2026-03-08.xlsx" in disposition_default, disposition_default

    resp_latest = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=latest")
    assert resp_latest.status_code == 200
    disposition_latest = unquote(resp_latest.headers.get("Content-Disposition", ""))
    assert "v7_2026-03-02至2026-03-08.xlsx" in disposition_latest, disposition_latest

    resp_invalid = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=abc", follow_redirects=True)
    assert resp_invalid.status_code == 200
    assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in resp_invalid.get_data(as_text=True)

    resp_zero = client.get("/scheduler/week-plan/export?week_start=2026-03-02&version=0", follow_redirects=True)
    assert resp_zero.status_code == 200
    assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in resp_zero.get_data(as_text=True)


def test_week_plan_no_history_page_empty_and_export_404(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False)
    client = app.test_client()

    page_resp = client.get("/scheduler/week-plan?week_start=2026-03-02")
    page_html = page_resp.get_data(as_text=True)
    assert page_resp.status_code == 200
    assert "暂无版本" in page_html
    assert 'aps-summary-value">v1' not in page_html
    assert 'aps-summary-value">v0' not in page_html

    export_resp = client.get("/scheduler/week-plan/export?week_start=2026-03-02")
    assert export_resp.status_code == 404
    assert "暂无排产历史" in export_resp.get_data(as_text=True)


def test_week_plan_export_uses_week_start_only_when_stale_range_present(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    calls = []

    def _fake_rows(self, **kwargs):
        calls.append(dict(kwargs))
        return {
            "rows": [
                {
                    "日期": "2026-05-11",
                    "批次号": "B001",
                    "图号": "P001",
                    "工序": 10,
                    "设备": "M001",
                    "人员": "OP001",
                    "时段": "08:00-10:00",
                }
            ],
            "version": 7,
            "status": "ok",
            "has_history": True,
            "week_start": "2026-05-11",
            "week_end": "2026-05-17",
        }

    monkeypatch.setattr(GanttService, "get_week_plan_rows", _fake_rows)

    resp = client.get(
        "/scheduler/week-plan/export"
        "?week_start=2026-05-11"
        "&start_date=2026-05-04"
        "&end_date=2026-05-10"
        "&version=7"
    )

    assert resp.status_code == 200
    assert calls == [{"week_start": "2026-05-11", "offset_weeks": 0, "version": "7"}]
    disposition = unquote(resp.headers.get("Content-Disposition", ""))
    assert "v7_2026-05-11至2026-05-17.xlsx" in disposition, disposition

    workbook = openpyxl.load_workbook(io.BytesIO(resp.data))
    sheet = workbook.active
    assert sheet["A2"].value == "2026-05-11"
    assert sheet["B2"].value == "B001"


def test_week_plan_export_failure_redirect_preserves_request_context(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    def _raise_export_failure(self, **kwargs):
        raise RuntimeError("forced export failure")

    monkeypatch.setattr(GanttService, "get_week_plan_rows", _raise_export_failure)

    resp = client.get(
        "/scheduler/week-plan/export"
        "?week_start=2026-05-11"
        "&offset=2"
        "&version=7"
        "&plan_role=baseline_best",
        follow_redirects=False,
    )

    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.path == "/scheduler/week-plan"
    assert query.get("week_start") == ["2026-05-11"]
    assert query.get("offset") == ["2"]
    assert query.get("version") == ["7"]
    assert query.get("plan_role") == ["baseline_best"]
    assert "forced export failure" not in location
