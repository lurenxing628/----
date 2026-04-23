from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, g, get_flashed_messages

from core.infrastructure.errors import ValidationError


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

    with app.test_request_context("/system/ui-mode"):
        assert utils_mod._safe_next_url("http://evil.example/x") is None
        assert utils_mod._safe_next_url("//evil.example/x") is None

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

    with app.test_request_context("/system/ui-mode"):
        assert utils_mod._safe_next_url(None) is None
        assert utils_mod._safe_next_url("   ") is None

    assert warnings == []


def _fake_url_for(endpoint, **values):
    if endpoint == "dashboard.index":
        return "/"
    if endpoint == "scheduler.config_page":
        return "/scheduler/config"
    if endpoint == "scheduler.batches_manage_page":
        return "/scheduler/batches"
    if endpoint == "scheduler.batch_detail":
        return f"/scheduler/batches/{values['batch_id']}"
    raise AssertionError(f"unexpected endpoint: {endpoint!r}")


def test_scheduler_config_invalid_next_uses_local_fallback(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_config as scheduler_config_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_config_mod, "url_for", _fake_url_for)

    cfg_svc = SimpleNamespace(
        apply_preset=lambda name: {
            "requested_preset": name,
            "effective_active_preset": name,
            "status": "applied",
            "adjusted_fields": [],
            "reason": None,
            "error_field": None,
            "error_message": None,
        },
        mark_active_preset_custom=lambda: None,
    )

    with app.test_request_context(
        "/scheduler/config/preset/apply",
        method="POST",
        data={"preset_name": "demo", "next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(config_service=cfg_svc)
        response = scheduler_config_mod.preset_apply()

    assert response.location.endswith("/scheduler/config")


def test_scheduler_batches_invalid_next_uses_local_success_and_failure_fallbacks(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_batches as scheduler_batches_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_batches_mod, "url_for", _fake_url_for)

    with app.test_request_context(
        "/scheduler/batches/B001/delete",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace(delete=lambda _batch_id: None))
        response = scheduler_batches_mod.delete_batch("B001")

    assert response.location.endswith("/scheduler/batches")

    def _raise_validation(_batch_id):
        raise ValidationError("删除失败", field="batch_id")

    with app.test_request_context(
        "/scheduler/batches/B001/delete",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace(delete=_raise_validation))
        response = scheduler_batches_mod.delete_batch("B001")

    assert response.location.endswith("/scheduler/batches/B001")


def test_system_ui_mode_invalid_next_prefers_same_origin_referrer_then_dashboard(monkeypatch) -> None:
    import web.routes.system_ui_mode as system_ui_mode_mod

    app = _build_app()
    monkeypatch.setattr(system_ui_mode_mod, "url_for", _fake_url_for)
    monkeypatch.setattr(
        system_ui_mode_mod,
        "_get_system_config_service",
        lambda: SimpleNamespace(set_value=lambda *args, **kwargs: None),
    )

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "http://evil.example/x"},
        environ_base={"HTTP_REFERER": "http://localhost/system/backup?tab=ops#frag"},
    ):
        response = system_ui_mode_mod.ui_mode_set()

    assert response.location.endswith("/system/backup?tab=ops")

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "http://evil.example/x"},
        environ_base={"HTTP_REFERER": "https://evil.example/system/backup"},
    ):
        response = system_ui_mode_mod.ui_mode_set()

    assert response.location.endswith("/")

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "http://evil.example/x"},
        environ_base={"HTTP_REFERER": "/system/backup"},
    ):
        response = system_ui_mode_mod.ui_mode_set()

    assert response.location.endswith("/system/backup")


@pytest.mark.parametrize(
    ("db_fails", "cookie_fails", "expected_category"),
    [
        (False, False, "success"),
        (True, False, "warning"),
        (False, True, "warning"),
        (True, True, "error"),
    ],
)
def test_system_ui_mode_flash_level_matches_db_and_cookie_outcome(
    monkeypatch, db_fails: bool, cookie_fails: bool, expected_category: str
) -> None:
    import web.routes.system_ui_mode as system_ui_mode_mod

    app = _build_app()
    warnings: list[str] = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    monkeypatch.setattr(system_ui_mode_mod, "url_for", _fake_url_for)

    if db_fails:
        monkeypatch.setattr(
            system_ui_mode_mod,
            "_get_system_config_service",
            lambda: SimpleNamespace(
                set_value=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db exploded"))
            ),
        )
    else:
        monkeypatch.setattr(
            system_ui_mode_mod,
            "_get_system_config_service",
            lambda: SimpleNamespace(set_value=lambda *args, **kwargs: None),
        )

    if cookie_fails:
        monkeypatch.setattr(
            app.response_class,
            "set_cookie",
            lambda self, *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cookie exploded")),
        )

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "/system/backup"},
    ):
        response = system_ui_mode_mod.ui_mode_set()
        flashes = get_flashed_messages(with_categories=True)

    assert response.location.endswith("/system/backup")
    assert [category for category, _message in flashes] == [expected_category]

    if not cookie_fails:
        assert any("aps_ui_mode=v2" in item for item in response.headers.getlist("Set-Cookie"))
    if db_fails:
        assert any("写入 UI 模式到 SystemConfig 失败" in msg for msg in warnings), warnings
    if cookie_fails:
        assert any("写入 UI 模式 cookie 失败" in msg for msg in warnings), warnings
    else:
        assert all("写入 UI 模式 cookie 失败" not in msg for msg in warnings), warnings
