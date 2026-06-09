"""回归测试：build_analysis_read_context 与 /scheduler/analysis 页面的读侧契约——无排产历史时 version_resolution.status=no_history、页面显示「暂无排产历史」；默认与 version=latest 都选中最新版本；显式存在版本保留其它版本于选择器；显式版本缺失时保留趋势区并提示 vN 无对应历史；result_summary 解析失败不崩页只记 warning；候选对比统计缺失时不查询方案角色（plan_role_options 为空）。"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

from core.infrastructure.database import ensure_schema, get_connection
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _EmptyHistoryService:
    def list_versions(self, limit: int = 50):
        return []

    def get_latest_version(self):
        return None

    def get_by_version(self, version: int):
        return None

    def list_recent(self, limit: int = 400):
        return []


class _HistoryItem:
    def __init__(self, version: int, summary: Dict[str, Any]):
        self.version = int(version)
        self._summary = dict(summary)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "strategy": "greedy",
            "result_status": "success",
            "result_summary": self._summary,
        }


class _SingleHistoryService:
    def __init__(self, summary: Dict[str, Any]):
        self.summary = dict(summary)

    def list_versions(self, limit: int = 50):
        return [{"version": 7, "strategy": "greedy", "result_status": "success"}]

    def get_latest_version(self):
        return 7

    def get_by_version(self, version: int):
        return _HistoryItem(int(version), self.summary)

    def list_recent(self, limit: int = 400):
        return [_HistoryItem(7, self.summary)]


class _PlanRoleServiceMustNotBeCalled:
    def list_plan_roles(self, version: int):
        raise AssertionError(f"缺少候选对比统计时不应该查询方案角色，version={version}")


def _reset_modules() -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    db_path = tmp_path / "aps_analysis_read.db"
    log_dir = tmp_path / "logs"
    backup_dir = tmp_path / "backups"
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    point_env_at_shared(monkeypatch)

    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    _reset_modules()
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(db_path)


def _insert_history(
    db_path: str,
    *,
    version: int,
    result_summary: Any = None,
    result_status: str = "success",
) -> None:
    summary = {"algo": {"metrics": {"overdue_count": 0, "makespan_hours": 8}}, "warnings": []}
    raw_summary = result_summary if result_summary is not None else json.dumps(summary, ensure_ascii=False)
    if isinstance(raw_summary, dict):
        raw_summary = json.dumps(raw_summary, ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(version), "greedy", 0, 0, result_status, raw_summary, "pytest"),
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


def _html(response) -> str:
    return response.get_data(as_text=True)


def _assert_selected_version(html: str, version: int) -> None:
    assert "版本概览" in html
    assert 'aps-summary-label">版本' in html
    assert f'aps-summary-value">v{version}' in html


def test_analysis_read_context_no_history_keeps_page_empty_and_resolution_no_history(tmp_path, monkeypatch) -> None:
    from web.routes.domains.scheduler.scheduler_analysis_read import build_analysis_read_context

    read_ctx = build_analysis_read_context(
        SimpleNamespace(schedule_history_query_service=_EmptyHistoryService()),
        raw_version=None,
    )

    assert read_ctx.version_resolution.status == "no_history"
    assert read_ctx.selected_version is None
    assert read_ctx.versions == []
    assert read_ctx.raw_hist == []

    app, _db_path = _build_app(tmp_path, monkeypatch)
    response = app.test_client().get("/scheduler/analysis")
    html = _html(response)

    assert response.status_code == 200
    assert "暂无排产历史" in html


def test_analysis_read_context_defaults_to_latest_version(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7)

    response = app.test_client().get("/scheduler/analysis")
    html = _html(response)

    assert response.status_code == 200
    _assert_selected_version(html, 7)


def test_analysis_read_context_latest_query_still_selects_latest(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7)

    response = app.test_client().get("/scheduler/analysis?version=latest")
    html = _html(response)

    assert response.status_code == 200
    _assert_selected_version(html, 7)


def test_analysis_read_context_explicit_existing_version_keeps_other_versions_in_picker(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=6)
    _insert_history(db_path, version=7)

    response = app.test_client().get("/scheduler/analysis?version=6")
    html = _html(response)

    assert response.status_code == 200
    _assert_selected_version(html, 6)
    assert 'value="7"' in html


def test_analysis_read_context_missing_explicit_version_keeps_trends_visible(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7)

    response = app.test_client().get("/scheduler/analysis?version=999")
    html = _html(response)

    assert response.status_code == 200
    assert "v999 无对应排产历史" in html
    assert 'aps-summary-value">v999' not in html


def test_analysis_read_context_invalid_summary_does_not_break_page(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7, result_summary="{broken json")
    warnings = _capture_warning_logs(app, monkeypatch)

    response = app.test_client().get("/scheduler/analysis?version=7")
    html = _html(response)

    assert response.status_code == 200
    assert "排产优化分析" in html
    assert any("排产分析页 排产摘要 解析失败（version=7, source=selected" in item for item in warnings)
    assert any("排产分析页 排产摘要 解析失败（version=7, source=trend" in item for item in warnings)


def test_analysis_read_context_does_not_query_plan_roles_without_candidate_count() -> None:
    from web.routes.domains.scheduler.scheduler_analysis_read import build_analysis_read_context

    summary = {
        "algo": {
            "metrics": {"overdue_count": 0},
            "candidate_comparison": {
                "enabled": True,
                "candidates": [],
            },
        }
    }

    read_ctx = build_analysis_read_context(
        SimpleNamespace(
            schedule_history_query_service=_SingleHistoryService(summary),
            schedule_plan_query_service=_PlanRoleServiceMustNotBeCalled(),
        ),
        raw_version="7",
    )

    assert read_ctx.selected_version == 7
    assert read_ctx.plan_role_options == []
    assert read_ctx.plan_role_integrity_notice == ""
