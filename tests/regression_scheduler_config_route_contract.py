from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g


class _ConfigServiceStub:
    def __init__(self) -> None:
        self.restore_default_called = False
        self.snapshot = {"sort_strategy": "priority_first"}

    def get_snapshot(self):
        return self.snapshot

    def get_available_strategies(self):
        return ["priority_first", "due_date_first"]

    def list_presets(self):
        return ["默认-稳定"]

    def get_active_preset(self):
        return "默认-稳定"

    def get_active_preset_reason(self):
        return "当前以手动设置为准。"

    def restore_default(self) -> None:
        self.restore_default_called = True


def _build_app(monkeypatch, config_service: _ConfigServiceStub) -> Flask:
    import web.routes.scheduler_config as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-config-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(config_service=config_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_config_route_uses_request_services(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    get_response = client.get("/scheduler/config")
    payload = get_response.get_json()

    assert get_response.status_code == 200
    assert payload["active_preset_reason"] == "当前以手动设置为准。"
    assert payload["builtin_presets"]

    post_response = client.post("/scheduler/config/default")

    assert post_response.status_code in (301, 302)
    assert config_service.restore_default_called is True
