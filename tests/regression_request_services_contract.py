from __future__ import annotations

from functools import cached_property

import pytest

import web.bootstrap.request_services as request_services_mod


def test_request_services_contract_without_flask_request_context(monkeypatch) -> None:
    expected_attrs = request_services_mod.REQUEST_SERVICES_PUBLIC_ATTRS
    public_cached_attrs = tuple(
        name
        for name, value in request_services_mod.RequestServices.__dict__.items()
        if isinstance(value, cached_property)
    )

    assert public_cached_attrs == expected_attrs
    assert "__slots__" not in request_services_mod.RequestServices.__dict__

    created = []

    class _StubBatchService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            created.append((logger, op_logger))
            self.logger = logger
            self.op_logger = op_logger

    monkeypatch.setattr(request_services_mod, "BatchService", _StubBatchService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: object(),
    )

    assert services.batch_service is services.batch_service
    assert created == [("app-logger", "op-logger")]

    with pytest.raises(AttributeError):
        getattr(services, "undefined_service")


def test_request_services_exposes_gantt_adjustment_validation_service(monkeypatch) -> None:
    created = []

    class _StubValidationService:
        def __init__(self, _conn, logger=None, **_kwargs):
            created.append(logger)

    monkeypatch.setattr(request_services_mod, "GanttAdjustmentValidationService", _StubValidationService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: object(),
    )

    assert services.gantt_adjustment_validation_service is services.gantt_adjustment_validation_service
    assert created == ["app-logger"]


def test_request_services_exposes_gantt_adjustment_publish_service(monkeypatch) -> None:
    created = []

    class _StubPublishService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            created.append((logger, op_logger))

    monkeypatch.setattr(request_services_mod, "GanttAdjustmentPublishService", _StubPublishService)

    services = request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=lambda: object(),
    )

    assert services.gantt_adjustment_publish_service is services.gantt_adjustment_publish_service
    assert created == [("app-logger", "op-logger")]
