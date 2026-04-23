from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional, cast

import pytest
from flask import Flask, Response, g, request

import web.bootstrap.factory as factory_mod
import web.error_boundary as error_boundary_mod
from web.bootstrap.entrypoint import create_app_with_mode

_BeforeHook = Callable[[], Any]
_AfterHook = Callable[[Response], Response]
_TeardownHook = Callable[[Optional[BaseException]], None]


class _StartedWriteFailG:
    def __init__(self) -> None:
        object.__setattr__(self, "_failed_once", False)

    def __setattr__(self, name, value):
        if name == "_aps_req_started" and not object.__getattribute__(self, "_failed_once"):
            object.__setattr__(self, "_failed_once", True)
            raise RuntimeError("started boom")
        object.__setattr__(self, name, value)

    def pop(self, name, default=None):
        return default

    def __contains__(self, key):
        return False


class _PathExplodingRequest:
    def __init__(self, real_request) -> None:
        self._real_request = real_request

    @property
    def path(self):
        raise RuntimeError("path boom")

    @property
    def accept_mimetypes(self):
        return self._real_request.accept_mimetypes

    @property
    def is_json(self):
        return self._real_request.is_json

    @property
    def headers(self):
        return self._real_request.headers

    @property
    def method(self):
        return self._real_request.method


class _HeadersExplodingRequest:
    def __init__(self, real_request) -> None:
        self._real_request = real_request

    @property
    def headers(self):
        raise RuntimeError("headers boom")

    @property
    def path(self):
        return self._real_request.path

    @property
    def method(self):
        return self._real_request.method


class _CloseBoomDb:
    def close(self) -> None:
        raise RuntimeError("close boom")


class _CloseAwareDb:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _PassThroughOperationLogger:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _NoopDb:
    def close(self) -> None:
        return None


def _build_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Flask:
    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "aps.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))
    monkeypatch.setenv("SECRET_KEY", "aps-factory-observability-test")
    monkeypatch.setattr(factory_mod, "_EXIT_BACKUP_REGISTERED", True)
    monkeypatch.setattr(factory_mod, "_EXIT_BACKUP_MANAGER", None)
    return create_app_with_mode("default")


def _get_before_hook(app: Flask, name: str) -> _BeforeHook:
    funcs = list(app.before_request_funcs.get(None, []))
    return cast(_BeforeHook, next(func for func in funcs if getattr(func, "__name__", "") == name))


def _get_after_hook(app: Flask, name: str) -> _AfterHook:
    funcs = list(app.after_request_funcs.get(None, []))
    return cast(_AfterHook, next(func for func in funcs if getattr(func, "__name__", "") == name))


def _get_teardown_hook(app: Flask, name: str) -> _TeardownHook:
    funcs = list(app.teardown_appcontext_funcs)
    return cast(_TeardownHook, next(func for func in funcs if getattr(func, "__name__", "") == name))


def _capture_warnings(monkeypatch: pytest.MonkeyPatch, app: Flask) -> list[str]:
    warnings: list[str] = []

    def _warning(message: str, *args: Any, **kwargs: Any) -> None:
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _warning)
    return warnings


def _capture_errors(monkeypatch: pytest.MonkeyPatch, app: Flask) -> list[str]:
    errors: list[str] = []

    def _error(message: str, *args: Any, **kwargs: Any) -> None:
        errors.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "error", _error)
    return errors


def _patch_request_services_probe(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {"count": 0}
    backend_calls: list[str] = []

    def _backend_factory() -> object:
        backend_calls.append("called")
        return object()

    class _RequestServicesProbe:
        def __init__(self, *, db: Any, app_logger: Any, op_logger: Any, get_excel_backend: Callable[[], Any]) -> None:
            captured["count"] = int(captured["count"] or 0) + 1
            captured["db"] = db
            captured["app_logger"] = app_logger
            captured["op_logger"] = op_logger
            captured["get_excel_backend"] = get_excel_backend

    monkeypatch.setattr(factory_mod, "get_excel_backend", _backend_factory)
    monkeypatch.setattr(factory_mod, "RequestServices", _RequestServicesProbe)
    return captured, backend_calls


def test_open_db_logs_started_write_failure_without_breaking_health_whitelist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    warnings = _capture_warnings(monkeypatch, app)

    monkeypatch.setattr(factory_mod, "g", _StartedWriteFailG())

    with app.test_request_context("/system/health"):
        result = open_db()

    assert result is None
    assert any("请求耗时起点记录失败" in message for message in warnings), warnings


def test_open_db_logs_request_whitelist_failure_and_keeps_main_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    close_db = _get_teardown_hook(app, "_close_db")
    warnings = _capture_warnings(monkeypatch, app)

    monkeypatch.setattr(factory_mod, "request", _PathExplodingRequest(request))
    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: False)

    with app.test_request_context("/probe"):
        first = open_db()
        assert first is None
        assert getattr(g, "db", None) is not None
        assert getattr(g, "services", None) is not None
        close_db(None)

    with app.test_request_context("/probe"):
        second = open_db()
        assert second is None
        assert getattr(g, "services", None) is not None
        close_db(None)

    matched = [message for message in warnings if "请求白名单判定失败，将继续主路径" in message]
    assert len(matched) == 1, warnings


def test_open_db_logs_maintenance_gate_response_classification_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    warnings = _capture_warnings(monkeypatch, app)

    monkeypatch.setattr(factory_mod, "request", _PathExplodingRequest(request))
    monkeypatch.setattr(error_boundary_mod, "request", _PathExplodingRequest(request))
    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: True)

    with app.test_request_context("/probe"):
        response = open_db()
        assert getattr(g, "db", None) is None
        assert getattr(g, "services", None) is None

    assert isinstance(response, tuple)
    assert response[1] == 503
    assert any("维护窗口响应分类失败" in message for message in warnings), warnings


@pytest.mark.parametrize("path", ["/static/demo.js", "/system/health", "/system/runtime/shutdown"])
def test_open_db_does_not_mount_request_services_for_whitelisted_paths(
    path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    with app.test_request_context(path):
        result = open_db()
        assert result is None
        assert getattr(g, "db", None) is None
        assert getattr(g, "op_logger", None) is None
        assert getattr(g, "services", None) is None

    assert captured["count"] == 0
    assert backend_calls == []


def test_open_db_mounts_request_services_after_maintenance_hook_without_calling_excel_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    close_db = _get_teardown_hook(app, "_close_db")
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    maintenance_called = {"value": False}

    class _MaintenanceProbe:
        @classmethod
        def run_if_due(cls, *_args: Any, **_kwargs: Any) -> None:
            maintenance_called["value"] = True

    import core.services.system as system_mod

    monkeypatch.setattr(system_mod, "SystemMaintenanceService", _MaintenanceProbe)

    with app.test_request_context("/scheduler/"):
        result = open_db()
        assert result is None
        assert maintenance_called["value"] is True
        assert captured["count"] == 1
        assert captured["db"] is g.db
        assert captured["app_logger"] is g.app_logger
        assert captured["op_logger"] is g.op_logger
        assert captured["get_excel_backend"] is factory_mod.get_excel_backend
        assert getattr(g, "services", None) is not None
        assert backend_calls == []
        close_db(None)


def test_open_db_does_not_mount_request_services_for_maintenance_short_circuit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: True)

    with app.test_request_context("/scheduler/"):
        response = open_db()
        assert isinstance(response, tuple)
        assert response[1] == 503
        assert getattr(g, "db", None) is None
        assert getattr(g, "services", None) is None

    assert captured["count"] == 0
    assert backend_calls == []


def test_open_db_returns_500_when_maintenance_detection_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    errors = _capture_errors(monkeypatch, app)
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with app.test_request_context("/scheduler/"):
        result = open_db()
        assert isinstance(result, tuple)
        assert result[1] == 500
        assert getattr(g, "db", None) is None
        assert getattr(g, "services", None) is None

    assert captured["count"] == 0
    assert backend_calls == []
    assert any("系统状态检测失败，已中止请求" in message for message in errors), errors


def test_open_db_returns_503_when_maintenance_response_construction_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    warnings = _capture_warnings(monkeypatch, app)
    errors = _capture_errors(monkeypatch, app)
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        factory_mod,
        "_maintenance_gate_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("render boom")),
    )

    with app.test_request_context("/scheduler/"):
        response = open_db()
        assert getattr(g, "db", None) is None
        assert getattr(g, "services", None) is None

    assert isinstance(response, tuple)
    assert response[1] == 503
    assert "系统正在维护中" in str(response[0])
    assert captured["count"] == 0
    assert backend_calls == []
    assert not any("维护窗口检测失败" in message for message in warnings), warnings
    assert any("维护窗口响应构造失败" in message for message in errors), errors


def test_open_db_mounts_request_services_when_maintenance_task_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    close_db = _get_teardown_hook(app, "_close_db")
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    class _MaintenanceProbe:
        @classmethod
        def run_if_due(cls, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("maintenance failed")

    import core.services.system as system_mod

    monkeypatch.setattr(system_mod, "SystemMaintenanceService", _MaintenanceProbe)

    with app.test_request_context("/scheduler/"):
        result = open_db()
        assert result is None
        assert getattr(g, "db", None) is not None
        assert getattr(g, "services", None) is not None
        close_db(None)

    assert captured["count"] == 1
    assert backend_calls == []


def test_open_db_raises_when_db_preseeded_but_services_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    captured, backend_calls = _patch_request_services_probe(monkeypatch)

    with app.test_request_context("/scheduler/"):
        g.db = _NoopDb()
        with pytest.raises(RuntimeError, match=r"g\.services"):
            open_db()
        assert getattr(g, "services", None) is None

    assert captured["count"] == 0
    assert backend_calls == []


def test_request_services_construction_failure_closes_local_db_and_preserves_error_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(tmp_path, monkeypatch)
    captured: dict[str, Any] = {}

    def _fake_get_connection(_db_path: str) -> _CloseAwareDb:
        db = _CloseAwareDb()
        captured["db"] = db
        return db

    class _ExplodingRequestServices:
        def __init__(self, **_kwargs: Any) -> None:
            raise RuntimeError("services boom")

    monkeypatch.setattr(factory_mod, "get_connection", _fake_get_connection)
    monkeypatch.setattr(factory_mod, "OperationLogger", _PassThroughOperationLogger)
    monkeypatch.setattr(factory_mod, "RequestServices", _ExplodingRequestServices)

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 500
    assert "服务器内部错误" in response.get_data(as_text=True)
    assert isinstance(captured.get("db"), _CloseAwareDb)
    assert captured["db"].close_calls == 1


def test_close_db_logs_cleanup_failure_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    close_db = _get_teardown_hook(app, "_close_db")
    warnings = _capture_warnings(monkeypatch, app)

    with app.app_context():
        g.db = _CloseBoomDb()
        close_db(None)

    with app.app_context():
        g.db = _CloseBoomDb()
        close_db(None)

    matched = [message for message in warnings if "数据库连接关闭失败" in message]
    assert len(matched) == 1, warnings


def test_perf_headers_logs_prefetch_detection_failure_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    perf_headers = _get_after_hook(app, "_perf_headers")
    warnings = _capture_warnings(monkeypatch, app)

    monkeypatch.setattr(factory_mod, "request", _HeadersExplodingRequest(request))

    with app.test_request_context("/probe"):
        g._aps_req_started = time.perf_counter() - 1.0
        resp = app.response_class("OK")
        perf_headers(resp)
        assert resp.headers.get("Server-Timing")

    with app.test_request_context("/probe"):
        g._aps_req_started = time.perf_counter() - 1.0
        resp = app.response_class("OK")
        perf_headers(resp)

    matched = [message for message in warnings if "预取请求判定失败" in message]
    assert len(matched) == 1, warnings


def test_perf_headers_logs_outer_failure_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    perf_headers = _get_after_hook(app, "_perf_headers")
    warnings = _capture_warnings(monkeypatch, app)

    with app.test_request_context("/probe"):
        g._aps_req_started = object()
        resp = app.response_class("OK")
        perf_headers(resp)

    with app.test_request_context("/probe"):
        g._aps_req_started = object()
        resp = app.response_class("OK")
        perf_headers(resp)

    matched = [message for message in warnings if "性能头写入失败" in message]
    assert len(matched) == 1, warnings
