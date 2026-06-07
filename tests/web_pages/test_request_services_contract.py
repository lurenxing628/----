"""契约测试：web.bootstrap.request_services.RequestServices 的惰性服务装配契约——公开服务属性集与 cached_property 声明一致且非 __slots__、各服务按需惰性构造并按请求缓存、按签名差异透传 app_logger/op_logger、excel backend 仅在访问 excel_service 时才取；失败传播上 AttributeError 转 RuntimeError 且不缓存失败、非 AttributeError 原样上抛同样不缓存。"""

from __future__ import annotations

from functools import cached_property

import pytest

import web.bootstrap.request_services as request_services_mod


def _make_services(*, get_excel_backend=lambda: object()):
    """Lightweight in-memory RequestServices factory shared by this cluster.

    被测对象纯内存:db=object() 占位,不触碰 DB/app fixture。
    """
    return request_services_mod.RequestServices(
        db=object(),
        app_logger="app-logger",
        op_logger="op-logger",
        get_excel_backend=get_excel_backend,
    )


# ---------------------------------------------------------------------------
# 契约元数据(cached_property 集合 + 非 __slots__)——非按服务循环,留独立函数。
# ---------------------------------------------------------------------------
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

    services = _make_services()

    assert services.batch_service is services.batch_service
    assert created == [("app-logger", "op-logger")]

    with pytest.raises(AttributeError):
        getattr(services, "undefined_service")


# ---------------------------------------------------------------------------
# 同构 expose 段参数化:仅折叠 (服务属性名, stub 类, 期望 created) 三个高度同构维度。
# 各服务签名差异(validation 仅 logger / publish 收 logger+op_logger)由 expected_created 区分,禁折叠成同一期望。
# ---------------------------------------------------------------------------
def _build_expose_stub(stub_kind, created):
    if stub_kind == "validation":

        class _StubValidationService:
            def __init__(self, _conn, logger=None, **_kwargs):
                created.append(logger)

        return _StubValidationService

    class _StubLoggerOpLoggerService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            created.append((logger, op_logger))

    return _StubLoggerOpLoggerService


@pytest.mark.parametrize(
    ("attr_name", "patch_target", "stub_kind", "expected_created"),
    [
        pytest.param(
            "gantt_adjustment_validation_service",
            "GanttAdjustmentValidationService",
            "validation",
            ["app-logger"],
            id="validation_service_logger_only",
        ),
        pytest.param(
            "gantt_adjustment_publish_service",
            "GanttAdjustmentPublishService",
            "logger_op_logger",
            [("app-logger", "op-logger")],
            id="publish_service_logger_and_op_logger",
        ),
    ],
)
def test_request_services_exposes_service(
    monkeypatch, attr_name, patch_target, stub_kind, expected_created
) -> None:
    created = []
    stub_class = _build_expose_stub(stub_kind, created)
    monkeypatch.setattr(request_services_mod, patch_target, stub_class)

    services = _make_services()

    assert getattr(services, attr_name) is getattr(services, attr_name)
    assert created == expected_created


# ---------------------------------------------------------------------------
# 失败传播(自 regression_request_services_failure_propagation.py 平移)——整体保留,禁参数化。
# AttributeError→RuntimeError 转换 + 不缓存失败 vs 非 AttributeError 原样上抛 + 不重试,语义对立。
# ---------------------------------------------------------------------------
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

    services = _make_services()

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

    services = _make_services()

    with pytest.raises(ValueError, match="boom"):
        _ = services.config_service

    assert calls["count"] == 1
    assert "config_service" not in services.__dict__


# ---------------------------------------------------------------------------
# 惰性构造(自 regression_request_services_lazy_construction.py 平移)——整体保留,禁参数化。
# config 不触发 backend(backend_calls == []) vs excel 触发 backend(backend_calls == ["called"]),对立面。
# excel 的 backend 是 keyword-only,与其它服务位置参 _conn 不同,不可与 config 参数化混用。
# ---------------------------------------------------------------------------
def test_request_services_is_lazy_and_caches_per_request(monkeypatch) -> None:
    created = []
    backend_calls = []

    class _StubConfigService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            created.append(("config", logger, op_logger))
            self.logger = logger
            self.op_logger = op_logger

    monkeypatch.setattr(request_services_mod, "ConfigService", _StubConfigService)

    services = _make_services(
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

    services = _make_services(
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
