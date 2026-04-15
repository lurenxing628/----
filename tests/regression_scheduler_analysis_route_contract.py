from __future__ import annotations

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


def _build_app(monkeypatch, history_service: _HistoryServiceStub) -> Flask:
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
    summary = {"algo": {"metrics": {"overdue_count": 1}}}
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
    assert history_service.version_limits == [50]
    assert history_service.version_queries == [3]
    assert history_service.recent_limits == [400]
