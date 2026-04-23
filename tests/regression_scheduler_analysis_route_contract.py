from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from flask import Flask, g


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

    def list_versions(self, limit=50):
        self.version_limits.append(limit)
        return [{"version": 3}]

    def get_by_version(self, version):
        self.version_queries.append(int(version))
        return _HistoryItem(int(version), self.summary)

    def list_recent(self, limit=400):
        self.recent_limits.append(limit)
        return [_HistoryItem(3, self.summary)]


class _MissingSelectedHistoryService(_HistoryServiceStub):
    def get_by_version(self, version):
        self.version_queries.append(int(version))
        return None


def _build_app(monkeypatch, history_service: _HistoryServiceStub) -> Flask:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    import web.routes.scheduler as _scheduler_routes  # noqa: F401
    import web.routes.scheduler_analysis as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-analysis-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(schedule_history_query_service=history_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_analysis_route_uses_request_services(monkeypatch) -> None:
    summary = {"warnings": ["冻结窗口存在跳批风险"], "algo": {"metrics": {"overdue_count": 1}}}
    history_service = _HistoryServiceStub(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["versions"][0]["version"] == 3
    assert payload["selected"]["version"] == 3
    assert payload["selected_summary"] == summary
    assert payload["trend_rows"][0]["version"] == 3
    assert payload["selected_summary_display"]["summary_parse_state"]["parse_failed"] is False
    assert payload["selected_summary_display"]["warning_total"] == 1
    assert payload["selected_summary_display"]["warnings_preview"] == ["冻结窗口存在跳批风险"]
    assert payload["trend_summary_state"] == {"incomplete": False, "parse_failed_count": 0}
    assert "objective_label_for" not in payload
    json.dumps(payload, ensure_ascii=False)
    assert history_service.version_limits == [50]
    assert history_service.version_queries == [3]
    assert history_service.recent_limits == [400]


def test_scheduler_analysis_route_marks_parse_failure_and_incomplete_trend(monkeypatch) -> None:
    history_service = _HistoryServiceStub("{broken json")
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected_summary"] == {}
    assert payload["selected_summary_display"]["summary_parse_state"]["parse_failed"] is True
    assert payload["trend_summary_state"] == {"incomplete": True, "parse_failed_count": 1}


def test_scheduler_analysis_route_surfaces_missing_requested_history(monkeypatch) -> None:
    summary = {"algo": {"metrics": {"overdue_count": 1}}}
    history_service = _MissingSelectedHistoryService(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=9")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected"]["version"] == 9
    assert payload["selected_summary"] is None
    assert payload["selected_history_resolution"]["requested_version"] == 9
    assert payload["selected_history_resolution"]["history_missing"] is True
    assert "9" in str(payload["selected_history_resolution"]["message"] or "")
    assert payload["trend_rows"][0]["version"] == 3
    assert history_service.version_queries == [9]
