from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

import pytest
from flask import Flask

import web.bootstrap.entrypoint as entrypoint_mod
from web.bootstrap.entrypoint import EntryPointDeps

_CreateApp = Callable[[], Flask]
_StringFactory = Callable[[], str]
_PathFactory = Callable[[str], str]
_AnyCallback = Callable[..., Any]
_PickBindHost = Callable[..., str]
_PickPort = Callable[..., Tuple[str, int]]
_StopRuntimeFromDir = Callable[..., int]
_ServeRuntimeApp = Callable[[Flask, str, int], Any]
_BoolSelector = Callable[[bool], bool]


class _Logger:
    def __init__(self, *, fail_levels=()) -> None:
        self.fail_levels: Set[str] = set(fail_levels)
        self.messages: List[Tuple[str, str]] = []

    def _log(self, level: str, message, *args) -> None:
        if level in self.fail_levels:
            raise RuntimeError(f"logger {level} boom")
        text = message % args if args else str(message)
        self.messages.append((level, text))

    def info(self, message, *args) -> None:
        self._log("info", message, *args)

    def warning(self, message, *args) -> None:
        self._log("warning", message, *args)

    def error(self, message, *args) -> None:
        self._log("error", message, *args)


class _App:
    def __init__(self, tmp_path: Path, *, debug: bool = False, fail_levels=()) -> None:
        self.config: Dict[str, Any] = {
            "DEBUG": bool(debug),
            "LOG_DIR": str(tmp_path / "logs"),
            "DATABASE_PATH": str(tmp_path / "aps.db"),
            "BACKUP_DIR": str(tmp_path / "backups"),
            "EXCEL_TEMPLATE_DIR": str(tmp_path / "templates_excel"),
            "APP_UI_MODE": "default",
        }
        self.logger = _Logger(fail_levels=fail_levels)
        self.run_calls: List[Dict[str, Any]] = []

    def run(self, *, host: str, port: int, debug: bool, use_reloader: bool) -> None:
        self.run_calls.append(
            {
                "host": str(host),
                "port": int(port),
                "debug": bool(debug),
                "use_reloader": bool(use_reloader),
            }
        )


def _make_state() -> Dict[str, List[Any]]:
    return {
        "clear_launch_error": [],
        "write_launch_error": [],
        "pick_port": [],
        "serve_runtime_app": [],
        "atexit": [],
    }


def _build_deps(
    app: _App,
    state: Dict[str, List[Any]],
    *,
    create_app: Optional[_CreateApp] = None,
    clear_launch_error: Optional[_AnyCallback] = None,
    write_launch_error: Optional[_AnyCallback] = None,
    current_runtime_owner: Optional[_StringFactory] = None,
    resolve_prelaunch_log_dir: Optional[_PathFactory] = None,
    acquire_runtime_lock: Optional[_AnyCallback] = None,
    release_runtime_lock: Optional[_AnyCallback] = None,
    delete_runtime_contract_files: Optional[_AnyCallback] = None,
    write_runtime_host_port_files: Optional[_AnyCallback] = None,
    write_runtime_contract_file: Optional[_AnyCallback] = None,
    default_chrome_profile_dir: Optional[_PathFactory] = None,
    pick_bind_host: Optional[_PickBindHost] = None,
    pick_port: Optional[_PickPort] = None,
    stop_runtime_from_dir: Optional[_StopRuntimeFromDir] = None,
    serve_runtime_app: Optional[_ServeRuntimeApp] = None,
    should_use_runtime_reloader: Optional[_BoolSelector] = None,
    should_own_runtime_resources: Optional[_BoolSelector] = None,
    should_register_runtime_lifecycle_handlers: Optional[_BoolSelector] = None,
    atexit_register: Optional[_AnyCallback] = None,
) -> EntryPointDeps:
    def _clear_launch_error(log_dir):
        state["clear_launch_error"].append(str(log_dir))

    def _write_launch_error(runtime_dir, message, log_dir):
        state["write_launch_error"].append((str(runtime_dir), str(message), None if log_dir is None else str(log_dir)))

    def _pick_bind_host(raw_host, logger=None):
        text = str(raw_host or "").strip()
        return text or "127.0.0.1"

    def _pick_port(host, preferred_port, logger=None):
        state["pick_port"].append((str(host), int(preferred_port)))
        return str(host), 6100

    def _serve_runtime_app(app_obj: Flask, host: str, port: int) -> None:
        state["serve_runtime_app"].append((app_obj, str(host), int(port)))

    def _create_app() -> Flask:
        return cast(Flask, app)

    def _current_runtime_owner() -> str:
        return "DOMAIN\\tester"

    def _resolve_prelaunch_log_dir(runtime_dir: str) -> str:
        return str(Path(runtime_dir) / "prelaunch-logs")

    def _default_chrome_profile_dir(runtime_dir: str) -> str:
        return str(Path(runtime_dir) / "chrome-profile")

    def _acquire_runtime_lock(*args: Any, **kwargs: Any) -> Dict[str, int]:
        return {"pid": 12345}

    def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    def _stop_runtime_from_dir(runtime_dir: str, stop_aps_chrome: bool = False) -> int:
        return 0

    def _always_false(debug: bool) -> bool:
        return False

    def _atexit_register(*args: Any, **kwargs: Any) -> None:
        state["atexit"].append((args, kwargs))

    return EntryPointDeps(
        create_app=create_app or _create_app,
        clear_launch_error=clear_launch_error or _clear_launch_error,
        write_launch_error=write_launch_error or _write_launch_error,
        current_runtime_owner=current_runtime_owner or _current_runtime_owner,
        resolve_prelaunch_log_dir=resolve_prelaunch_log_dir or _resolve_prelaunch_log_dir,
        acquire_runtime_lock=acquire_runtime_lock or _acquire_runtime_lock,
        release_runtime_lock=release_runtime_lock or _noop,
        delete_runtime_contract_files=delete_runtime_contract_files or _noop,
        write_runtime_host_port_files=write_runtime_host_port_files or _noop,
        write_runtime_contract_file=write_runtime_contract_file or _noop,
        default_chrome_profile_dir=default_chrome_profile_dir or _default_chrome_profile_dir,
        pick_bind_host=pick_bind_host or _pick_bind_host,
        pick_port=pick_port or _pick_port,
        stop_runtime_from_dir=stop_runtime_from_dir or _stop_runtime_from_dir,
        serve_runtime_app=serve_runtime_app or _serve_runtime_app,
        should_use_runtime_reloader=should_use_runtime_reloader or _always_false,
        should_own_runtime_resources=should_own_runtime_resources or _always_false,
        should_register_runtime_lifecycle_handlers=should_register_runtime_lifecycle_handlers or _always_false,
        atexit_register=atexit_register or _atexit_register,
    )


def test_clear_launch_error_failure_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    app = _App(tmp_path)
    state = _make_state()
    deps = _build_deps(
        app,
        state,
        clear_launch_error=lambda log_dir: (_ for _ in ()).throw(RuntimeError("clear boom")),
    )

    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 0
    assert "清理历史启动错误文件失败" in capsys.readouterr().err


def test_create_app_failure_write_launch_error_failure_visible(capsys) -> None:
    state = _make_state()
    deps = EntryPointDeps(
        create_app=lambda: (_ for _ in ()).throw(RuntimeError("app boom")),
        clear_launch_error=lambda *args, **kwargs: None,
        write_launch_error=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("launch file boom")),
        current_runtime_owner=lambda: "DOMAIN\\tester",
        resolve_prelaunch_log_dir=lambda runtime_dir: str(Path(runtime_dir) / "prelaunch-logs"),
        acquire_runtime_lock=lambda *args, **kwargs: None,
        release_runtime_lock=lambda *args, **kwargs: None,
        delete_runtime_contract_files=lambda *args, **kwargs: None,
        write_runtime_host_port_files=lambda *args, **kwargs: None,
        write_runtime_contract_file=lambda *args, **kwargs: None,
        default_chrome_profile_dir=lambda runtime_dir: str(Path(runtime_dir) / "chrome-profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred_port, logger=None: (host, 6100),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: 0,
        serve_runtime_app=lambda app, host, port: None,
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: False,
        should_register_runtime_lifecycle_handlers=lambda debug: False,
        atexit_register=lambda *args, **kwargs: state["atexit"].append((args, kwargs)),
    )

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    stderr_text = capsys.readouterr().err
    assert rc == 14
    assert "应用启动失败：app boom" in stderr_text
    assert "写入启动错误文件失败" in stderr_text


def test_invalid_aps_port_logs_warning_and_uses_default_preferred_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _App(tmp_path)
    state = _make_state()
    deps = _build_deps(app, state)

    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.setenv("APS_PORT", "not-a-port")

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 0
    assert state["pick_port"][0][1] == 5000
    assert any("APS_PORT='not-a-port' 非法" in text for level, text in app.logger.messages if level == "warning")


class _ReadonlyEnv(dict):
    def __setitem__(self, key, value):
        if key in {"APS_HOST", "APS_PORT"}:
            raise OSError("env readonly")
        return super().__setitem__(key, value)


def test_env_write_failure_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _App(tmp_path)
    state = _make_state()
    deps = _build_deps(app, state)
    env = _ReadonlyEnv({"APS_HOST": "127.0.0.1", "APS_PORT": "6200"})

    monkeypatch.setattr(entrypoint_mod.os, "environ", env)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 0
    assert any("回写 APS_HOST/APS_PORT 环境变量失败" in text for level, text in app.logger.messages if level == "warning")


def test_host_fallback_warning_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _App(tmp_path)
    state = _make_state()
    deps = _build_deps(
        app,
        state,
        pick_port=lambda host, preferred_port, logger=None: ("127.0.0.1", 6100),
    )

    monkeypatch.setenv("APS_HOST", "192.0.2.10")
    monkeypatch.delenv("APS_PORT", raising=False)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 0
    assert any("APS_HOST=192.0.2.10 不可绑定" in text for level, text in app.logger.messages if level == "warning")


def test_acquire_runtime_lock_meta_failure_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _App(tmp_path)
    state = _make_state()
    deps = _build_deps(
        app,
        state,
        should_own_runtime_resources=lambda debug: True,
        acquire_runtime_lock=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("lock boom")),
        write_launch_error=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("launch file boom")),
    )

    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 13
    assert any("获取运行时锁失败：lock boom，但写入启动错误文件失败：launch file boom" in text for level, text in app.logger.messages if level == "error")


def test_configure_runtime_contract_meta_failure_visible_when_logger_error_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    app = _App(tmp_path, fail_levels={"error"})
    state = _make_state()
    deps = _build_deps(
        app,
        state,
        should_own_runtime_resources=lambda debug: True,
        write_runtime_host_port_files=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("contract boom")),
        write_launch_error=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("launch file boom")),
    )

    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    stderr_text = capsys.readouterr().err
    assert rc == 15
    assert "写入运行时契约失败：contract boom" in stderr_text
    assert "写入启动错误文件失败" in stderr_text


def test_parent_skip_info_visible_when_logger_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    app = _App(tmp_path, fail_levels={"info"})
    state = _make_state()
    deps = _build_deps(app, state)

    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)

    rc = entrypoint_mod.app_main(anchor_file=__file__, argv=[], deps=deps)

    assert rc == 0
    assert "开发重载父进程跳过获取运行时锁与运行时契约" in capsys.readouterr().err
