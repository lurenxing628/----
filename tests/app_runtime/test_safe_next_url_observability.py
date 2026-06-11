"""回归测试：_safe_next_url 对非法 next 跳转参数（绝对 URL、协议相对 URL）每请求只 warning 一次、对缺失/空白值不告警；scheduler config/batches 路由在 next 非法时回退到本地 url_for 端点。（system ui-mode 路由已随 2026-06 双轨退役删除，其专属用例一并移除。）"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List

from flask import Flask, g

from core.infrastructure.errors import ValidationError


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "aps-safe-next-observability"
    return app


def test_safe_next_url_logs_invalid_non_empty_value_once_per_request(monkeypatch) -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    warnings: List[str] = []

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
    warnings: List[str] = []

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


