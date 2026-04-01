"""
回归测试：debug reloader 父/子进程的运行态 ownership。

验证点：
1) debug reloader 父进程不获取运行时锁，也不写运行时契约。
2) debug reloader 子进程会获取运行时锁、写运行时契约，并注册清理。
3) 非 debug 启动仍会获取运行时锁，且走 serve_runtime_app。
4) `app.py` / `app_new_ui.py` 两个入口行为一致。
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_aps_logger_handlers() -> None:
    for logger_name in ("APS", "web.bootstrap.factory"):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def _prepare_import_env(tmpdir: str) -> dict[str, str]:
    db_path = str(Path(tmpdir) / "aps.db")
    log_dir = str(Path(tmpdir) / "logs")
    backup_dir = str(Path(tmpdir) / "backups")
    template_dir = str(Path(tmpdir) / "templates_excel")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    Path(template_dir).mkdir(parents=True, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = db_path
    os.environ["APS_LOG_DIR"] = log_dir
    os.environ["APS_BACKUP_DIR"] = backup_dir
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = template_dir
    os.environ["SECRET_KEY"] = "aps-runtime-lock-reloader-test-key"
    os.environ.pop("WERKZEUG_RUN_MAIN", None)
    os.environ.pop("APS_HOST", None)
    os.environ.pop("APS_PORT", None)
    return {
        "DATABASE_PATH": db_path,
        "LOG_DIR": log_dir,
        "BACKUP_DIR": backup_dir,
        "EXCEL_TEMPLATE_DIR": template_dir,
    }


def _load_entry_module(module_name: str):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _new_state() -> dict[str, list]:
    return {
        "atexit": [],
        "clear_launch_error": [],
        "write_launch_error": [],
        "acquire_runtime_lock": [],
        "write_runtime_host_port_files": [],
        "write_runtime_contract_file": [],
        "serve_runtime_app": [],
        "app_run": [],
        "logs": [],
    }


class _FakeLogger:
    def __init__(self, state: dict[str, list]) -> None:
        self._state = state

    def info(self, message: str) -> None:
        self._state["logs"].append(("info", str(message)))

    def warning(self, message: str) -> None:
        self._state["logs"].append(("warning", str(message)))

    def error(self, message: str) -> None:
        self._state["logs"].append(("error", str(message)))


class _FakeApp:
    def __init__(self, *, debug: bool, ui_mode: str, paths: dict[str, str], state: dict[str, list]) -> None:
        self.config = {
            "DEBUG": bool(debug),
            "APP_UI_MODE": str(ui_mode),
            "DATABASE_PATH": paths["DATABASE_PATH"],
            "LOG_DIR": paths["LOG_DIR"],
            "BACKUP_DIR": paths["BACKUP_DIR"],
            "EXCEL_TEMPLATE_DIR": paths["EXCEL_TEMPLATE_DIR"],
        }
        self.logger = _FakeLogger(state)
        self._state = state

    def run(self, *, host: str, port: int, debug: bool, use_reloader: bool) -> None:
        self._state["app_run"].append(
            {
                "host": str(host),
                "port": int(port),
                "debug": bool(debug),
                "use_reloader": bool(use_reloader),
            }
        )


def _patch_entry_module(mod, fake_app: _FakeApp, state: dict[str, list]):
    original_atexit_register = mod.atexit.register

    def _fake_atexit_register(func, *args, **kwargs):
        state["atexit"].append(
            {
                "name": getattr(func, "__name__", repr(func)),
                "args": args,
                "kwargs": kwargs,
            }
        )
        return func

    def _fake_acquire_runtime_lock(*args, **kwargs):
        state["acquire_runtime_lock"].append({"args": args, "kwargs": kwargs})
        return {"pid": 12345}

    def _fake_write_runtime_host_port_files(*args, **kwargs):
        state["write_runtime_host_port_files"].append({"args": args, "kwargs": kwargs})

    def _fake_write_runtime_contract_file(*args, **kwargs):
        state["write_runtime_contract_file"].append({"args": args, "kwargs": kwargs})
        return os.path.join(fake_app.config["LOG_DIR"], "aps_runtime.json")

    def _fake_clear_launch_error(*args, **kwargs):
        state["clear_launch_error"].append({"args": args, "kwargs": kwargs})

    def _fake_write_launch_error(*args, **kwargs):
        state["write_launch_error"].append({"args": args, "kwargs": kwargs})

    def _fake_serve_runtime_app(app, host: str, port: int) -> None:
        state["serve_runtime_app"].append({"app": app, "host": str(host), "port": int(port)})

    mod.atexit.register = _fake_atexit_register
    mod.create_app = lambda: fake_app
    mod.clear_launch_error = _fake_clear_launch_error
    mod.write_launch_error = _fake_write_launch_error
    mod.acquire_runtime_lock = _fake_acquire_runtime_lock
    mod.write_runtime_host_port_files = _fake_write_runtime_host_port_files
    mod.write_runtime_contract_file = _fake_write_runtime_contract_file
    mod.pick_bind_host = lambda raw_host, logger=None: "127.0.0.1"
    mod.pick_port = lambda host, preferred_port, logger=None: ("127.0.0.1", 58123)
    mod.current_runtime_owner = lambda: "DOMAIN\\user"
    mod.serve_runtime_app = _fake_serve_runtime_app
    return original_atexit_register


def _execute_case(module_name: str, *, ui_mode: str, debug: bool, run_main: str | None):
    tmpdir = tempfile.mkdtemp(prefix=f"aps_regression_runtime_lock_{module_name}_")
    paths = _prepare_import_env(tmpdir)
    mod = _load_entry_module(module_name)
    state = _new_state()
    fake_app = _FakeApp(debug=debug, ui_mode=ui_mode, paths=paths, state=state)
    original_atexit_register = _patch_entry_module(mod, fake_app, state)

    if run_main is None:
        os.environ.pop("WERKZEUG_RUN_MAIN", None)
    else:
        os.environ["WERKZEUG_RUN_MAIN"] = str(run_main)

    try:
        rc = mod.main([])
    finally:
        mod.atexit.register = original_atexit_register
        _reset_aps_logger_handlers()
        logging.shutdown()
        sys.modules.pop(module_name, None)
    return rc, state, fake_app


def _assert_parent_case(module_name: str, ui_mode: str) -> None:
    rc, state, fake_app = _execute_case(module_name, ui_mode=ui_mode, debug=True, run_main=None)
    if rc != 0:
        raise RuntimeError(f"{module_name} debug 父进程返回非 0：{rc}")
    if state["acquire_runtime_lock"]:
        raise RuntimeError(f"{module_name} debug 父进程不应获取运行时锁")
    if state["write_runtime_host_port_files"] or state["write_runtime_contract_file"]:
        raise RuntimeError(f"{module_name} debug 父进程不应写运行时契约")
    if state["serve_runtime_app"]:
        raise RuntimeError(f"{module_name} debug 父进程不应走 serve_runtime_app")
    if len(state["app_run"]) != 1 or state["app_run"][0]["use_reloader"] is not True:
        raise RuntimeError(f"{module_name} debug 父进程应走 app.run(use_reloader=True)")
    if state["atexit"]:
        raise RuntimeError(f"{module_name} debug 父进程不应注册运行态清理：{state['atexit']!r}")
    if "APS_RUNTIME_SHUTDOWN_TOKEN" in fake_app.config:
        raise RuntimeError(f"{module_name} debug 父进程不应生成运行时 shutdown token")
    if state["write_launch_error"]:
        raise RuntimeError(f"{module_name} debug 父进程不应写启动错误：{state['write_launch_error']!r}")
    if os.environ.get("APS_HOST") != "127.0.0.1" or os.environ.get("APS_PORT") != "58123":
        raise RuntimeError(f"{module_name} debug 父进程应为子进程注入固定 host/port")


def _assert_child_case(module_name: str, ui_mode: str) -> None:
    rc, state, fake_app = _execute_case(module_name, ui_mode=ui_mode, debug=True, run_main="true")
    if rc != 0:
        raise RuntimeError(f"{module_name} debug 子进程返回非 0：{rc}")
    if len(state["acquire_runtime_lock"]) != 1:
        raise RuntimeError(f"{module_name} debug 子进程应获取一次运行时锁：{state['acquire_runtime_lock']!r}")
    if len(state["write_runtime_host_port_files"]) != 1 or len(state["write_runtime_contract_file"]) != 1:
        raise RuntimeError(f"{module_name} debug 子进程应写完整运行时契约")
    if state["serve_runtime_app"]:
        raise RuntimeError(f"{module_name} debug 子进程不应走 serve_runtime_app")
    if len(state["app_run"]) != 1 or state["app_run"][0]["use_reloader"] is not True:
        raise RuntimeError(f"{module_name} debug 子进程应走 app.run(use_reloader=True)")
    registered = [item["name"] for item in state["atexit"]]
    if registered != ["release_runtime_lock", "delete_runtime_contract_files"]:
        raise RuntimeError(f"{module_name} debug 子进程注册的清理函数不符合预期：{registered!r}")
    if not str(fake_app.config.get("APS_RUNTIME_SHUTDOWN_TOKEN") or "").strip():
        raise RuntimeError(f"{module_name} debug 子进程应生成 shutdown token")
    if fake_app.config.get("APS_RUNTIME_OWNER") != "DOMAIN\\user":
        raise RuntimeError(f"{module_name} debug 子进程 owner 不正确：{fake_app.config!r}")
    if str(fake_app.config.get("APP_UI_MODE") or "") != ui_mode:
        raise RuntimeError(f"{module_name} debug 子进程 ui_mode 不正确：{fake_app.config!r}")
    contract_call = state["write_runtime_contract_file"][0]
    if str(contract_call["kwargs"].get("ui_mode") or "") != ui_mode:
        raise RuntimeError(f"{module_name} debug 子进程 contract ui_mode 不正确：{contract_call!r}")
    if state["write_launch_error"]:
        raise RuntimeError(f"{module_name} debug 子进程不应写启动错误：{state['write_launch_error']!r}")


def _assert_production_case(module_name: str, ui_mode: str) -> None:
    rc, state, fake_app = _execute_case(module_name, ui_mode=ui_mode, debug=False, run_main=None)
    if rc != 0:
        raise RuntimeError(f"{module_name} 非 debug 启动返回非 0：{rc}")
    if len(state["acquire_runtime_lock"]) != 1:
        raise RuntimeError(f"{module_name} 非 debug 启动应获取运行时锁：{state['acquire_runtime_lock']!r}")
    if len(state["write_runtime_host_port_files"]) != 1 or len(state["write_runtime_contract_file"]) != 1:
        raise RuntimeError(f"{module_name} 非 debug 启动应写完整运行时契约")
    if state["app_run"]:
        raise RuntimeError(f"{module_name} 非 debug 启动不应走 app.run：{state['app_run']!r}")
    if len(state["serve_runtime_app"]) != 1:
        raise RuntimeError(f"{module_name} 非 debug 启动应走 serve_runtime_app：{state['serve_runtime_app']!r}")
    registered = [item["name"] for item in state["atexit"]]
    if registered != ["release_runtime_lock", "delete_runtime_contract_files"]:
        raise RuntimeError(f"{module_name} 非 debug 启动注册的清理函数不符合预期：{registered!r}")
    if not str(fake_app.config.get("APS_RUNTIME_SHUTDOWN_TOKEN") or "").strip():
        raise RuntimeError(f"{module_name} 非 debug 启动应生成 shutdown token")
    if state["write_launch_error"]:
        raise RuntimeError(f"{module_name} 非 debug 启动不应写启动错误：{state['write_launch_error']!r}")


def main() -> None:
    _assert_parent_case("app", "default")
    _assert_child_case("app", "default")
    _assert_production_case("app", "default")

    _assert_parent_case("app_new_ui", "new_ui")
    _assert_child_case("app_new_ui", "new_ui")
    _assert_production_case("app_new_ui", "new_ui")
    print("OK")


if __name__ == "__main__":
    main()
