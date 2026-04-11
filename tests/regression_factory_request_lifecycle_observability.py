from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional, cast

import pytest
from flask import Flask, Response, g, request

import web.bootstrap.factory as factory_mod
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
        close_db(None)

    with app.test_request_context("/probe"):
        second = open_db()
        assert second is None
        close_db(None)

    matched = [message for message in warnings if "请求白名单判定失败，将继续主路径" in message]
    assert len(matched) == 1, warnings


def test_open_db_logs_maintenance_gate_response_classification_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    warnings = _capture_warnings(monkeypatch, app)

    monkeypatch.setattr(factory_mod, "request", _PathExplodingRequest(request))
    monkeypatch.setattr(factory_mod, "is_maintenance_window_active", lambda *args, **kwargs: True)

    with app.test_request_context("/probe"):
        response = open_db()
        assert getattr(g, "db", None) is None

    assert isinstance(response, tuple)
    assert response[1] == 503
    assert any("维护窗口响应分类失败" in message for message in warnings), warnings


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
