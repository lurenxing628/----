from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from web.error_handlers import register_error_handlers

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _HistoryItem:
    def __init__(self, version: int, summary):
        self.version = int(version)
        self._summary = summary

    def to_dict(self):
        return {"version": self.version, "result_summary": self._summary}


class _HistoryServiceStub:
    def __init__(self, summary):
        self.summary = summary
        self.version_limits = []
        self.version_queries = []
        self.recent_limits = []

    def list_versions(self, limit=30):
        self.version_limits.append(limit)
        return [{"version": 3}]

    def get_by_version(self, version):
        self.version_queries.append(int(version))
        return _HistoryItem(int(version), self.summary)

    def list_recent(self, limit=20):
        self.recent_limits.append(limit)
        return [_HistoryItem(3, self.summary)]


class _HistoryServiceSelectiveStub(_HistoryServiceStub):
    def __init__(self, summary, *, existing_versions=None):
        super().__init__(summary)
        self.existing_versions = {int(version) for version in (existing_versions or {3})}

    def get_by_version(self, version):
        self.version_queries.append(int(version))
        if int(version) not in self.existing_versions:
            return None
        return _HistoryItem(int(version), self.summary)


def _build_app(monkeypatch, history_service: _HistoryServiceStub) -> Flask:
    import web.routes.system as _system_routes  # noqa: F401
    import web.routes.system_history as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-system-history-route"
    app.register_blueprint(route_mod.bp, url_prefix="/system")
    register_error_handlers(app)

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(schedule_history_query_service=history_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def _build_real_app(tmp_path, monkeypatch, *, summary_obj) -> Flask:
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
        (3, "priority_first", 1, 1, "partial", json.dumps(summary_obj, ensure_ascii=False), "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_system_history_route_uses_request_services(monkeypatch) -> None:
    summary = {
        "warnings": ["资源池已降级"],
        "degradation_events": [
            {
                "code": "resource_pool_degraded",
                "message": "自动分配资源池构建失败，本次排产已降级为不自动分配资源。",
                "count": 1,
            }
        ],
        "algo": {"metrics": {"overdue_count": 1}},
    }
    history_service = _HistoryServiceStub(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/system/history?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["versions"][0]["version"] == 3
    assert payload["selected"]["version"] == 3
    assert payload["selected_summary"] == summary
    assert payload["selected_summary_display"]["warning_total"] == 1
    assert payload["selected_summary_display"]["warnings_preview"] == ["资源池已降级"]
    assert payload["selected_summary_display"]["warning_hidden_count"] == 0
    assert payload["selected_summary_display"]["primary_degradation"]["details"] == ["资源池构建已降级"]
    assert payload["selected_summary_display"]["secondary_degradation_messages"][0]["code"] == "resource_pool_degraded"
    assert payload["items"][0]["result_summary_obj"] == summary
    assert payload["items"][0]["result_summary_display"]["warning_total"] == 1
    assert payload["items"][0]["result_summary_display"]["warnings_preview"] == ["资源池已降级"]
    assert payload["items"][0]["result_summary_display"]["secondary_degradation_messages"][0]["code"] == "resource_pool_degraded"
    assert history_service.version_limits == [30]
    assert history_service.version_queries == [3]
    assert history_service.recent_limits == [20]


def test_system_history_route_exposes_warning_pipeline_display(monkeypatch) -> None:
    summary = {
        "warnings": ["资源池已降级"],
        "degraded_causes": ["summary_merge_failed"],
        "degradation_events": [{"code": "summary_merge_failed", "message": "", "count": 1}],
        "algo": {
            "warning_pipeline": {
                "algo_warning_count": 2,
                "summary_warning_count": 0,
                "summary_merge_attempted": True,
                "summary_merge_failed": True,
                "summary_merge_error": "summary_warnings_assignment_failed",
            }
        },
    }
    history_service = _HistoryServiceStub(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/system/history?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected_summary_display"]["warning_pipeline_display"] == {
        "source": "warning_pipeline",
        "message": "摘要告警合并已降级。",
        "note": "摘要告警未能完整合并到历史摘要。",
        "summary_merge_failed": True,
        "summary_merge_error": "summary_warnings_assignment_failed",
        "algo_warning_count": 2,
        "summary_warning_count": 0,
    }
    assert payload["items"][0]["result_summary_display"]["warning_pipeline_display"]["source"] == "warning_pipeline"


def test_system_history_route_zero_and_negative_versions_keep_exact_query_semantics(monkeypatch) -> None:
    history_service = _HistoryServiceSelectiveStub({}, existing_versions={3})
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    zero_resp = client.get("/system/history?version=0")
    zero_payload = zero_resp.get_json()
    negative_resp = client.get("/system/history?version=-1")
    negative_payload = negative_resp.get_json()

    assert zero_resp.status_code == 200
    assert zero_payload["filters"]["version"] == "0"
    assert zero_payload["selected"] is None

    assert negative_resp.status_code == 200
    assert negative_payload["filters"]["version"] == "-1"
    assert negative_payload["selected"] is None

    assert history_service.version_queries == [0, -1]


def test_system_history_route_rejects_non_integer_version(monkeypatch) -> None:
    history_service = _HistoryServiceSelectiveStub({}, existing_versions={3})
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/system/history?version=abc", headers={"Accept": "application/json"})

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["code"] == "1001"
    assert "version 不合法（期望整数）" in payload["error"]["message"]


def test_system_history_page_renders_warning_pipeline_guard_html(tmp_path, monkeypatch) -> None:
    summary = {
        "warnings": ["资源池已降级"],
        "degraded_causes": ["summary_merge_failed"],
        "degradation_events": [{"code": "summary_merge_failed", "message": "", "count": 1}],
        "algo": {
            "warning_pipeline": {
                "algo_warning_count": 2,
                "summary_warning_count": 0,
                "summary_merge_attempted": True,
                "summary_merge_failed": True,
                "summary_merge_error": "summary_warnings_assignment_failed",
            }
        },
    }
    app = _build_real_app(tmp_path, monkeypatch, summary_obj=summary)
    client = app.test_client()

    response = client.get("/system/history?version=3")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "摘要告警合并状态：已降级" in html
    assert "算法告警：2 条" in html
    assert "摘要告警：0 条" in html
    assert "摘要告警未能完整合并到历史摘要。" in html
    assert html.count("算法告警：2 条") == 1
    assert "告警 1 条" in html
    assert "调试详情：原始摘要" in html
