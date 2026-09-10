"""守护双开防线时序合同：运行时锁必须先于 create_app 的一切共享库副作用（ensure_schema 迁移、
atexit 退出备份注册）——锁被占的第二实例必须在 create_app 之前以 rc=13 退出，绝不触库、绝不挂退出备份；
锁成功路径上 acquire_lock → atexit(release) → create_app 的顺序不许重排。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask

import web.bootstrap.entrypoint as entrypoint_mod
from web.bootstrap.entrypoint import EntryPointDeps


def _make_deps(tmp_path: Path, events: List[str], state: Dict[str, Any], *, acquire_raises: bool) -> EntryPointDeps:
    def _acquire(*args: Any, **kwargs: Any):
        events.append("acquire_lock")
        if acquire_raises:
            raise RuntimeError("锁被另一实例持有")
        return {"pid": os.getpid()}

    def _create_app() -> Flask:
        events.append("create_app")
        app = Flask("lock-order-test")
        app.config.update(
            DEBUG=False,
            DATABASE_PATH=str(tmp_path / "db" / "aps.db"),
            LOG_DIR=str(tmp_path / "logs"),
            BACKUP_DIR=str(tmp_path / "backups"),
            EXCEL_TEMPLATE_DIR=str(tmp_path / "templates_excel"),
        )
        return app

    def _atexit_register(func: Any, *args: Any, **kwargs: Any) -> Any:
        state["atexit"].append(getattr(func, "__name__", repr(func)))
        events.append(f"atexit:{getattr(func, '__name__', repr(func))}")
        return func

    return EntryPointDeps(
        create_app=_create_app,
        clear_launch_error=lambda *a, **k: None,
        write_launch_error=lambda *a, **k: state["write_launch_error"].append(a),
        current_runtime_owner=lambda: "LOCALBOX\\tester",
        resolve_prelaunch_log_dir=lambda runtime_dir: str(tmp_path / "prelaunch-logs"),
        acquire_runtime_lock=_acquire,
        release_runtime_lock=lambda *a, **k: None,
        delete_runtime_contract_files=lambda *a, **k: None,
        write_runtime_host_port_files=lambda *a, **k: None,
        write_runtime_contract_file=lambda *a, **k: str(tmp_path / "logs" / "aps_runtime.json"),
        default_chrome_profile_dir=lambda runtime_dir: str(tmp_path / "chrome-profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred_port, logger=None: (host, 6321),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: 0,
        serve_runtime_app=lambda app, host, port: events.append("serve"),
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        should_register_runtime_lifecycle_handlers=lambda debug: True,
        atexit_register=_atexit_register,
        resolve_startup_debug_flag=lambda: False,
    )


def test_lock_rejected_second_instance_exits_before_any_db_side_effect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)
    events: List[str] = []
    state: Dict[str, Any] = {"atexit": [], "write_launch_error": []}
    deps = _make_deps(tmp_path, events, state, acquire_raises=True)

    rc = entrypoint_mod.app_main(anchor_file=str(tmp_path / "app.py"), argv=[], deps=deps)

    assert rc == 13
    assert "create_app" not in events, "锁被占的第二实例绝不许执行 create_app（含 ensure_schema 迁移与退出备份注册）"
    assert events == ["acquire_lock"], f"锁失败后不许有任何后续副作用: {events}"
    assert state["atexit"] == [], "锁失败路径不许注册任何 atexit 清理/备份"


def test_lock_acquired_before_create_app_in_success_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)
    events: List[str] = []
    state: Dict[str, Any] = {"atexit": [], "write_launch_error": []}
    deps = _make_deps(tmp_path, events, state, acquire_raises=False)

    rc = entrypoint_mod.app_main(anchor_file=str(tmp_path / "app.py"), argv=[], deps=deps)

    assert rc == 0
    assert events.index("acquire_lock") < events.index("create_app"), f"锁必须先于 create_app: {events}"
    assert events.index("create_app") < events.index("serve")
    # atexit(release_runtime_lock) 必须紧跟锁成功、先于 create_app（崩溃后锁能被清理）
    first_atexit_pos = events.index([e for e in events if e.startswith("atexit:")][0])
    assert events.index("acquire_lock") < first_atexit_pos < events.index("create_app"), events
