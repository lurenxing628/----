from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, g

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import run_complex_excel_cases_e2e as complex_mod
import run_real_db_replay_e2e as replay_mod


class _NoopDb:
    def close(self) -> None:
        return None


class _CloseAwareDb:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _NoopOperationLogger:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


def _get_before_hook(app: Flask, name: str):
    for func in app.before_request_funcs.get(None) or []:
        if getattr(func, "__name__", "") == name:
            return func
    raise AssertionError(f"未找到 before_request 钩子：{name}")


def _patch_test_app_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.infrastructure.database as db_mod
    import core.infrastructure.logging as logging_mod
    import core.services.common.excel_templates as template_mod
    import web.error_handlers as err_mod
    import web.ui_mode as ui_mode_mod

    monkeypatch.setattr(db_mod, "ensure_schema", _noop)
    monkeypatch.setattr(logging_mod, "OperationLogger", _NoopOperationLogger)
    monkeypatch.setattr(template_mod, "ensure_excel_templates", _noop)
    monkeypatch.setattr(err_mod, "register_error_handlers", _noop)
    monkeypatch.setattr(ui_mode_mod, "init_ui_mode", _noop)


def _build_replay_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Flask:
    _patch_test_app_dependencies(monkeypatch)
    return replay_mod._create_test_app(
        repo_root=REPO_ROOT,
        db_path=tmp_path / "replay.db",
        log_dir=tmp_path / "logs",
        backup_dir=tmp_path / "backups",
        template_dir=tmp_path / "templates_excel",
    )


def _build_complex_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Flask:
    _patch_test_app_dependencies(monkeypatch)
    return complex_mod.create_test_app(
        repo_root=str(REPO_ROOT),
        db_path=str(tmp_path / "complex.db"),
        log_dir=str(tmp_path / "logs"),
        backup_dir=str(tmp_path / "backups"),
        template_dir=str(tmp_path / "templates_excel"),
    )


@pytest.mark.parametrize(
    "builder",
    [_build_replay_app, _build_complex_app],
)
def test_custom_test_app_open_db_raises_when_db_preseeded_but_services_missing(
    builder: Callable[[Path, pytest.MonkeyPatch], Flask],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = builder(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")

    with app.test_request_context("/scheduler/"):
        g.db = _NoopDb()
        with pytest.raises(RuntimeError, match=r"g\.services"):
            open_db()
        assert g.app_logger is app.logger
        assert getattr(g, "services", None) is None


@pytest.mark.parametrize(
    "builder",
    [_build_replay_app, _build_complex_app],
)
def test_custom_test_app_open_db_closes_local_db_when_request_services_mount_fails(
    builder: Callable[[Path, pytest.MonkeyPatch], Flask],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.infrastructure.database as db_mod
    import web.bootstrap.request_services as request_services_mod

    captured: dict[str, Any] = {}

    class _ExplodingRequestServices:
        def __init__(self, **_kwargs: Any) -> None:
            raise RuntimeError("services boom")

    monkeypatch.setattr(db_mod, "get_connection", lambda _db_path: captured.setdefault("db", _CloseAwareDb()))
    monkeypatch.setattr(
        request_services_mod,
        "RequestServices",
        _ExplodingRequestServices,
    )

    app = builder(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")
    with app.test_request_context("/scheduler/"):
        with pytest.raises(RuntimeError, match="services boom"):
            open_db()
        assert captured["db"].close_calls == 1
        assert getattr(g, "db", None) is None and getattr(g, "services", None) is None


@pytest.mark.parametrize(
    ("builder", "path"),
    [
        (_build_replay_app, "/static/demo.js"),
        (_build_replay_app, "/system/health"),
        (_build_replay_app, "/system/runtime/shutdown"),
        (_build_complex_app, "/static/demo.js"),
        (_build_complex_app, "/system/health"),
        (_build_complex_app, "/system/runtime/shutdown"),
    ],
)
def test_custom_test_app_open_db_short_circuits_whitelisted_paths_without_mounting_services(builder, path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = builder(tmp_path, monkeypatch)
    open_db = _get_before_hook(app, "_open_db")

    with app.test_request_context(path):
        assert open_db() is None
        assert getattr(g, "db", None) is None
        assert getattr(g, "services", None) is None
