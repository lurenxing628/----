"""同库多实例冲突在启动触库前被拒绝。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from flask import Flask

import web.bootstrap.entrypoint as entrypoint_mod
import web.bootstrap.launcher_runtime_lock as lock_mod
from web.bootstrap.entrypoint import EntryPointDeps
from web.bootstrap.launcher_paths import db_scope_lock_path, resolve_runtime_db_path

_OWNER = "LOCALBOX\\tester"


def _acquire(runtime_dir: Path, log_dir: Path, db: Path) -> Dict[str, Any]:
    return lock_mod.acquire_runtime_lock(
        str(runtime_dir),
        str(log_dir),
        owner=_OWNER,
        exe_path=sys.executable,
        db_path=str(db),
    )


def test_diverged_lock_namespace_same_db_second_instance_rejected(tmp_path: Path) -> None:
    """核心合同：锁命名空间（日志目录）分叉 + 同 DB 路径 → 第二实例必须被 db-scope 锁拒启。"""
    db = tmp_path / "shared" / "db" / "aps.db"
    logs1 = tmp_path / "inst1-logs"
    logs2 = tmp_path / "inst2-logs"

    _acquire(tmp_path / "inst1", logs1, db)
    assert (logs1 / "aps_runtime.lock").exists()
    db_lock = Path(db_scope_lock_path(str(db)))
    assert db_lock.exists(), "db-scope 锁必须建立在 DB 同路径"

    with pytest.raises(lock_mod.RuntimeLockError) as exc_info:
        _acquire(tmp_path / "inst2", logs2, db)

    assert "数据库" in str(exc_info.value), "拒启原因必须点名数据库被占用"
    assert not (logs2 / "aps_runtime.lock").exists(), "db 锁冲突后第二实例的壳锁必须回滚，不留残迹"
    assert (logs1 / "aps_runtime.lock").exists(), "第一实例的壳锁不受影响"
    assert f"pid={os.getpid()}" in db_lock.read_text(encoding="utf-8"), "db-scope 锁仍归第一实例"

    lock_mod.release_runtime_lock(str(logs1), db_path=str(db))


def _make_real_lock_deps(tmp_path: Path, events: List[str], state: Dict[str, Any], *, prelaunch_log_dir: Path) -> EntryPointDeps:
    def _create_app() -> Flask:
        events.append("create_app")
        return Flask("db-scope-lock-entrypoint-test")

    def _atexit_register(func: Any, *args: Any, **kwargs: Any) -> Any:
        state["atexit"].append({"name": getattr(func, "__name__", repr(func)), "args": args})
        return func

    return EntryPointDeps(
        create_app=_create_app,
        clear_launch_error=lambda *a, **k: None,
        write_launch_error=lambda *a, **k: None,
        current_runtime_owner=lambda: _OWNER,
        resolve_prelaunch_log_dir=lambda runtime_dir: str(prelaunch_log_dir),
        acquire_runtime_lock=lock_mod.acquire_runtime_lock,
        release_runtime_lock=lock_mod.release_runtime_lock,
        delete_runtime_contract_files=lambda *a, **k: None,
        write_runtime_host_port_files=lambda *a, **k: None,
        write_runtime_contract_file=lambda *a, **k: "",
        default_chrome_profile_dir=lambda runtime_dir: str(tmp_path / "chrome-profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred_port, logger=None: (host, 6322),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: 0,
        serve_runtime_app=lambda app, host, port: events.append("serve"),
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        should_register_runtime_lifecycle_handlers=lambda debug: True,
        atexit_register=_atexit_register,
        resolve_startup_debug_flag=lambda: False,
        resolve_runtime_db_path=resolve_runtime_db_path,
    )


def test_app_main_rejects_second_instance_on_db_conflict_before_create_app(tmp_path: Path, monkeypatch) -> None:
    """入口级合同：模拟锁命名空间分叉（不同锁目录）+ APS_DB_PATH 指向同一 DB，
    第二实例必须在 create_app（触库副作用）之前以 rc=13 被拒，且不残留自己的壳锁。"""
    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.delenv("APS_PORT", raising=False)
    db = tmp_path / "shared" / "db" / "aps.db"
    monkeypatch.setenv("APS_DB_PATH", str(db))

    # 第一实例：真实获取壳锁 + db-scope 锁（锁目录 logs1）
    logs1 = tmp_path / "inst1-logs"
    lock_mod.acquire_runtime_lock(
        str(tmp_path / "inst1"),
        str(logs1),
        owner=_OWNER,
        exe_path=sys.executable,
        db_path=str(db),
    )

    # 第二实例：走 app_main，锁命名空间落在另一个目录（源码态 lock_scope=runtime_dir/logs）
    inst2_dir = tmp_path / "inst2"
    inst2_dir.mkdir()
    events: List[str] = []
    state: Dict[str, Any] = {"atexit": []}
    deps = _make_real_lock_deps(tmp_path, events, state, prelaunch_log_dir=tmp_path / "inst2-prelaunch")

    rc = entrypoint_mod.app_main(anchor_file=str(inst2_dir / "app.py"), argv=[], deps=deps)

    assert rc == 13, "同库第二实例必须以锁失败返回码退出"
    assert "create_app" not in events, "被拒的第二实例绝不许执行 create_app（含迁移/退出备份注册）"
    assert state["atexit"] == [], "锁失败路径不许注册任何清理回调"
    assert not (inst2_dir / "logs" / "aps_runtime.lock").exists(), "第二实例的壳锁必须回滚"
    assert f"pid={os.getpid()}" in Path(db_scope_lock_path(str(db))).read_text(encoding="utf-8")

    lock_mod.release_runtime_lock(str(logs1), db_path=str(db))
