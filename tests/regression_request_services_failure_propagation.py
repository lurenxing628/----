from __future__ import annotations

import pytest

import web.bootstrap.request_services as request_services_mod


def test_request_services_converts_attribute_error_and_does_not_cache_failure(monkeypatch) -> None:
    calls = {"count": 0}

    class _FlakyBatchService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise AttributeError("repo missing")
            self.logger = logger
            self.op_logger = op_logger

    monkeypatch.setattr(request_services_mod, "BatchService", _FlakyBatchService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: object(),
    )

    with pytest.raises(RuntimeError, match=r"RequestServices\.batch_service"):
        _ = services.batch_service

    assert "batch_service" not in services.__dict__

    recovered = services.batch_service
    assert isinstance(recovered, _FlakyBatchService)
    assert services.batch_service is recovered
    assert calls["count"] == 2


def test_request_services_propagates_non_attribute_error_without_cache(monkeypatch) -> None:
    calls = {"count": 0}

    class _ExplodingConfigService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            calls["count"] += 1
            raise ValueError("boom")

    monkeypatch.setattr(request_services_mod, "ConfigService", _ExplodingConfigService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: object(),
    )

    with pytest.raises(ValueError, match="boom"):
        _ = services.config_service

    assert calls["count"] == 1
    assert "config_service" not in services.__dict__
