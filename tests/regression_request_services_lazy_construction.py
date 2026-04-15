from __future__ import annotations

import web.bootstrap.request_services as request_services_mod


def test_request_services_is_lazy_and_caches_per_request(monkeypatch) -> None:
    created = []
    backend_calls = []

    class _StubConfigService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            created.append(("config", logger, op_logger))
            self.logger = logger
            self.op_logger = op_logger

    monkeypatch.setattr(request_services_mod, "ConfigService", _StubConfigService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: backend_calls.append("called") or object(),
    )

    assert created == []
    assert backend_calls == []
    assert "config_service" not in services.__dict__

    first = services.config_service
    second = services.config_service

    assert first is second
    assert created == [("config", "app-logger", "op-logger")]
    assert backend_calls == []
    assert "config_service" in services.__dict__


def test_request_services_excel_service_uses_request_logger_and_backend_is_still_lazy(monkeypatch) -> None:
    created = []
    backend_calls = []

    class _StubExcelService:
        def __init__(self, *, backend, logger=None, op_logger=None, **_kwargs):
            created.append((backend, logger, op_logger))
            self.backend = backend
            self.logger = logger
            self.op_logger = op_logger

    monkeypatch.setattr(request_services_mod, "ExcelService", _StubExcelService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: backend_calls.append("called") or "backend-token",
    )

    assert created == []
    assert backend_calls == []
    assert "excel_service" not in services.__dict__

    first = services.excel_service
    second = services.excel_service

    assert first is second
    assert backend_calls == ["called"]
    assert created == [("backend-token", "app-logger", "op-logger")]
    assert "excel_service" in services.__dict__
