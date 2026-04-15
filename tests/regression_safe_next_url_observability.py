from __future__ import annotations

from flask import Flask


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "aps-safe-next-observability"
    return app


def test_safe_next_url_logs_invalid_non_empty_value_once_per_request(monkeypatch) -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    warnings: list[str] = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    monkeypatch.setattr(utils_mod, "url_for", lambda endpoint, **_kwargs: "/" if endpoint == "dashboard.index" else f"/{endpoint}")

    with app.test_request_context("/system/ui-mode"):
        dashboard_url = "/"
        assert utils_mod._safe_next_url("http://evil.example/x") == dashboard_url
        assert utils_mod._safe_next_url("//evil.example/x") == dashboard_url

    assert len(warnings) == 1, warnings
    assert "检测到非法 next 跳转参数" in warnings[0]
    assert "absolute_url" in warnings[0] or "protocol_relative" in warnings[0]


def test_safe_next_url_does_not_log_when_value_is_missing(monkeypatch) -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    warnings: list[str] = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    monkeypatch.setattr(utils_mod, "url_for", lambda endpoint, **_kwargs: "/" if endpoint == "dashboard.index" else f"/{endpoint}")

    with app.test_request_context("/system/ui-mode"):
        dashboard_url = "/"
        assert utils_mod._safe_next_url(None) == dashboard_url
        assert utils_mod._safe_next_url("   ") == dashboard_url

    assert warnings == []
