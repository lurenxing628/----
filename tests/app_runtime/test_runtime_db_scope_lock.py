"""同库多实例冲突在启动触库前被拒绝。"""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

import pytest
from flask import Flask

import web.bootstrap.entrypoint as entrypoint_mod
import web.bootstrap.launcher_runtime_lock as lock_mod
from core.infrastructure.safe_files import write_fixed_json
from web.bootstrap import launcher_cleanup_result as cleanup_mod
from web.bootstrap import launcher_contracts as contracts_mod
from web.bootstrap import launcher_stop as stop_mod
from web.bootstrap.entrypoint import EntryPointDeps
from web.bootstrap.launcher_lock_result import read_runtime_lock_result
from web.bootstrap.launcher_paths import db_scope_lock_path, default_chrome_profile_dir, resolve_runtime_db_path
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime

_OWNER = "LOCALBOX\\tester"
_LOGGER = logging.getLogger(__name__)


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

    first = _acquire(tmp_path / "inst1", logs1, db)
    assert (logs1 / "aps_runtime.lock").exists()
    db_lock = Path(db_scope_lock_path(str(db)))
    assert db_lock.exists(), "db-scope 锁必须建立在 DB 同路径"

    with pytest.raises(lock_mod.RuntimeLockError) as exc_info:
        _acquire(tmp_path / "inst2", logs2, db)

    assert "数据库" in str(exc_info.value), "拒启原因必须点名数据库被占用"
    assert not (logs2 / "aps_runtime.lock").exists(), "db 锁冲突后第二实例的壳锁必须回滚，不留残迹"
    assert (logs1 / "aps_runtime.lock").exists(), "第一实例的壳锁不受影响"
    assert f"pid={os.getpid()}" in db_lock.read_text(encoding="utf-8"), "db-scope 锁仍归第一实例"

    lock_mod.release_runtime_lock(str(logs1), expected_payload=first)


def _replace_stale_database_lock(runtime_dir, log_dir, database, entered, resume, installed, finish, results):
    original_probe = lock_mod._raise_if_runtime_lock_active

    def pause_stale_probe(existing, *args, **kwargs):
        if existing.get("owner") == "stale-owner":
            entered.set()
            if not resume.wait(10):
                raise RuntimeError("stale replacement synchronization timed out")
        return original_probe(existing, *args, **kwargs)

    lock_mod._raise_if_runtime_lock_active = pause_stale_probe
    payload = None
    try:
        payload = _acquire(Path(runtime_dir), Path(log_dir), Path(database))
        results.put(("acquired", payload))
        installed.set()
        if not finish.wait(10):
            raise RuntimeError("ownership verification synchronization timed out")
    except Exception as exc:
        results.put(("failure", str(exc)))
        installed.set()
        raise
    finally:
        if payload is not None:
            lock_mod.release_runtime_lock(log_dir, expected_payload=payload)


def _contend_for_database_lock(runtime_dir, log_dir, database, results):
    try:
        payload = _acquire(Path(runtime_dir), Path(log_dir), Path(database))
    except lock_mod.RuntimeLockError as exc:
        results.put(("rejected", str(exc)))
    else:
        results.put(("unexpected_acquire", payload))
        lock_mod.release_runtime_lock(log_dir, expected_payload=payload)


@pytest.mark.skipif(os.name != "posix", reason="POSIX real process mutation guard")
def test_stale_database_lock_replacement_excludes_competing_process(tmp_path):
    database = tmp_path / "shared" / "aps.db"
    database.parent.mkdir()
    database_lock = Path(db_scope_lock_path(str(database)))
    stale = dict(pid=99999999, owner="stale-owner", exe_path=sys.executable,
                 started_at="2000-01-01T00:00:00Z", db_path=str(database))
    with lock_mod.runtime_lock_mutation_guard(str(database_lock)):
        assert lock_mod._create_new_runtime_lock(str(database_lock), stale)
    context = multiprocessing.get_context("spawn")
    entered, resume, installed, finish = (context.Event() for _ in range(4))
    results = context.Queue()
    logs1, logs2 = tmp_path / "first-logs", tmp_path / "second-logs"
    first = context.Process(target=_replace_stale_database_lock,
                            args=(str(tmp_path / "first"), str(logs1), str(database), entered,
                                  resume, installed, finish, results))
    second = context.Process(target=_contend_for_database_lock,
                             args=(str(tmp_path / "second"), str(logs2), str(database), results))
    try:
        first.start()
        assert entered.wait(10), "先行进程必须在guard内进入陈旧归属判断"
        second.start()
        second.join(10)
        assert second.exitcode == 0, "竞争进程必须立即结束，不等待先行处理完成"
        state, message = results.get(timeout=3)
        assert state == "rejected" and "另一启动或退出操作正在处理运行锁" in message
        assert not (logs2 / "aps_runtime.lock").exists(), "失败竞争者回滚自身壳锁"
        assert lock_mod.read_runtime_lock_result_from_path(str(database_lock)).payload["owner"] == "stale-owner"
        resume.set()
        assert installed.wait(10)
        state, payload = results.get(timeout=3)
        assert state == "acquired", payload
        assert payload["pid"] == first.pid
        assert lock_mod.read_runtime_lock_result_from_path(str(database_lock)).payload["pid"] == first.pid
        assert read_runtime_lock_result(str(logs1)).payload["pid"] == first.pid
        assert not (logs2 / "aps_runtime.lock").exists()
        finish.set()
        first.join(10)
        assert first.exitcode == 0
        assert not database_lock.exists() and not (logs1 / "aps_runtime.lock").exists()
        assert Path(str(database_lock) + ".guard").is_file()
        assert Path(str(database_lock) + ".guard").read_bytes() == b""
    finally:
        resume.set()
        finish.set()
        for process in (first, second):
            if process.pid is not None:
                process.join(3)
                if process.is_alive():
                    process.terminate()
                    process.join(3)
        results.close()


def _distinct_lock_starts(monkeypatch):
    original = lock_mod._runtime_lock_payload
    issued = []

    def payload(*args, **kwargs):
        value = original(*args, **kwargs)
        issued.append(value)
        value["started_at"] = f"2020-01-01T00:00:{len(issued):02d}Z"
        return value

    monkeypatch.setattr(lock_mod, "_runtime_lock_payload", payload)


def _publish_claim(runtime_dir, logs, database, claim, instance_id):
    return contracts_mod.write_runtime_contract_file(
        str(runtime_dir), "127.0.0.1", 6322, db_path=str(database), shutdown_token="isolated-test-token",
        instance_id=instance_id, ui_mode="new_ui", log_dir=str(logs), backup_dir=str(runtime_dir / "backups"),
        excel_template_dir=str(runtime_dir / "templates"), owner=_OWNER, exe_path=sys.executable,
        chrome_profile_dir=default_chrome_profile_dir(str(runtime_dir)), logger=_LOGGER, expected_lock=claim,
    )


def test_cleanup_rechecks_mirror_and_preserves_new_primary_instance(tmp_path, monkeypatch):
    _distinct_lock_starts(monkeypatch)
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "primary-logs", tmp_path / "aps.db"
    old_lock = _acquire(runtime_dir, logs, database)
    old_contract = _publish_claim(runtime_dir, logs, database, old_lock, "old-instance")["payload"]
    mirror = runtime_dir / "logs"
    mirror_path = mirror / "aps_runtime.json"
    new_mirror = dict(old_contract, instance_id="new-mirror-instance", started_at="2020-01-01T00:01:00Z")
    original_match = cleanup_mod._matching_contract_error

    def replace_after_discovery(directory, payload):
        error = original_match(directory, payload)
        if not error and Path(directory) == mirror:
            with lock_mod.runtime_lock_mutation_guard(str(mirror / "aps_runtime.lock")):
                write_fixed_json(mirror_path, new_mirror)
        return error

    monkeypatch.setattr(cleanup_mod, "_matching_contract_error", replace_after_discovery)
    result = cleanup_mod.delete_runtime_contract_files_result(
        str(logs), expected_lock=old_lock, expected_contract=old_contract,
    )
    assert not result.ok and any(failure.reason == "ownership_changed" for failure in result.failures)
    assert contracts_mod.read_runtime_contract_result(str(mirror)).payload["instance_id"] == "new-mirror-instance"
    assert not (logs / "aps_runtime.json").exists()
    assert (logs / "aps_runtime.lock").is_file()
    assert all(not path.endswith("aps_runtime.lock") for path in result.attempted_paths)
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=old_lock)

    new_lock = _acquire(runtime_dir, logs, database)
    publication = _publish_claim(runtime_dir, logs, database, new_lock, "new-primary-instance")
    saved = Path(publication["path"]).read_bytes()
    result = cleanup_mod.delete_runtime_contract_files_result(str(logs), expected_lock=old_lock, expected_contract=old_contract)
    assert not result.ok and any(failure.reason == "ownership_changed" for failure in result.failures)
    assert Path(publication["path"]).read_bytes() == saved
    assert read_runtime_lock_result(str(logs)).payload["started_at"] == new_lock["started_at"]
    assert lock_mod.read_runtime_lock_result_from_path(db_scope_lock_path(str(database))).payload["started_at"] == new_lock["db_lock"]["started_at"]
    assert not lock_mod.release_runtime_lock(str(logs), expected_payload=old_lock)
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=new_lock)


def test_unmanaged_exit_uses_original_three_identities_after_backup(tmp_path, monkeypatch):
    _distinct_lock_starts(monkeypatch)
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "app" / "logs", tmp_path / "aps.db"
    configured_logs = tmp_path / "configured-logs"
    callbacks, events, state = [], [], {}

    def register(callback, *args, **kwargs):
        callbacks.append((callback, args, kwargs))
        return callback

    deps = replace(entrypoint_mod._default_deps("default"), atexit_register=register,
                   resolve_runtime_db_path=lambda directory: str(database))
    assert entrypoint_mod._acquire_runtime_lock_before_app(
        deps, runtime_dir=str(runtime_dir), lock_scope_target=str(runtime_dir), lock_scope_log_dir=None,
        runtime_owner=_OWNER, prelaunch_log_dir=str(logs), runtime_lock_state=state,
    ) is None
    register(lambda: events.append("backup"))
    app = Flask("original-exit")
    app.config.update(LOG_DIR=str(configured_logs), DATABASE_PATH=str(database), BACKUP_DIR=str(runtime_dir / "backups"),
                      EXCEL_TEMPLATE_DIR=str(runtime_dir / "templates"), APP_UI_MODE="new_ui")
    assert entrypoint_mod._publish_runtime_contract(
        deps, app, runtime_dir=str(runtime_dir), host="127.0.0.1", port=6322,
        runtime_owner=_OWNER, lock_state=state,
    ) is None
    assert len(callbacks) == 2
    assert state["contract_cleanup_dir"] == str(logs)
    assert state["contract"]["data_dirs"]["log_dir"] == str(configured_logs)
    for filename in ("aps_runtime.json", "aps_host.txt", "aps_port.txt", "aps_db_path.txt"):
        assert (logs / filename).read_bytes() == (configured_logs / filename).read_bytes()
    assert len({state["payload"]["started_at"], state["payload"]["db_lock"]["started_at"], state["contract"]["started_at"]}) == 3
    for callback, args, kwargs in reversed(callbacks):
        callback(*args, **kwargs)
    assert events == ["backup"]
    assert not (logs / "aps_runtime.lock").exists() and not Path(db_scope_lock_path(str(database))).exists()
    assert not (logs / "aps_runtime.json").exists()
    assert not (configured_logs / "aps_runtime.json").exists()

    repeated = cleanup_mod.delete_runtime_contract_files_result(
        str(logs), expected_lock=state["payload"], expected_contract=state["contract"],
    )
    assert repeated.ok, "服务退出已删除镜像契约，停止命令重复清理应成功"
    assert str(configured_logs / "aps_runtime.json") in repeated.missing_paths

    new_lock = _acquire(runtime_dir, logs, database)
    publication = _publish_claim(runtime_dir, logs, database, new_lock, "new-exit-instance")
    current = Path(publication["path"]).read_bytes()
    callback, args, kwargs = callbacks[0]
    with pytest.raises(lock_mod.RuntimeLockError, match="原实例运行时文件清理失败"):
        callback(*args, **kwargs)
    assert Path(publication["path"]).read_bytes() == current
    assert read_runtime_lock_result(str(logs)).payload["started_at"] == new_lock["started_at"]
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=new_lock)


def test_stop_retains_initial_shell_database_and_contract_through_wait(tmp_path, monkeypatch):
    _distinct_lock_starts(monkeypatch)
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "app" / "logs", tmp_path / "aps.db"
    old_lock = _acquire(runtime_dir, logs, database)
    old_contract = _publish_claim(runtime_dir, logs, database, old_lock, "old-stop-instance")["payload"]
    original_status = dict(state="active", runtime_dir=str(runtime_dir), state_dir=str(logs), lock=old_lock, contract=old_contract)
    new = {}
    monkeypatch.setattr(stop_mod, "_classify_runtime_state", lambda directory: original_status)
    monkeypatch.setattr(stop_mod, "_request_runtime_shutdown", lambda *args, **kwargs: True)

    def wait_and_replace(*args):
        assert lock_mod.release_runtime_lock(str(logs), expected_payload=old_lock)
        new["lock"] = _acquire(runtime_dir, logs, database)
        new["publication"] = _publish_claim(runtime_dir, logs, database, new["lock"], "new-stop-instance")
        return dict(state="stale", state_dir=str(logs), endpoint_up=False, lock=new["lock"], contract=new["publication"]["payload"])

    monkeypatch.setattr(stop_mod, "_wait_for_runtime_stop", wait_and_replace)
    assert stop_mod.stop_runtime_from_dir(str(runtime_dir)) == 1
    assert contracts_mod.read_runtime_contract_result(str(logs)).payload["instance_id"] == "new-stop-instance"
    assert read_runtime_lock_result(str(logs)).payload["started_at"] == new["lock"]["started_at"]
    assert lock_mod.read_runtime_lock_result_from_path(db_scope_lock_path(str(database))).payload["started_at"] == new["lock"]["db_lock"]["started_at"]
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=new["lock"])


def test_stop_succeeds_after_server_exit_cleans_configured_log_mirror(tmp_path, monkeypatch):
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "app" / "logs", tmp_path / "aps.db"
    configured_logs = tmp_path / "configured-logs"
    claim = _acquire(runtime_dir, logs, database)
    publication = _publish_claim(runtime_dir, configured_logs, database, claim, "normal-stop-instance")
    contract = publication["payload"]
    active = dict(state="active", runtime_dir=str(runtime_dir), state_dir=str(logs), lock=claim, contract=contract)
    monkeypatch.setattr(stop_mod, "_classify_runtime_state", lambda directory: active)
    monkeypatch.setattr(stop_mod, "_request_runtime_shutdown", lambda *args, **kwargs: True)

    def server_exits(*args):
        result = cleanup_mod.delete_runtime_contract_files_result(
            str(logs), expected_lock=claim, expected_contract=contract,
        )
        assert result.ok
        assert lock_mod.release_runtime_lock(str(logs), expected_payload=claim)
        return dict(state="absent", state_dir=str(logs), endpoint_up=False, lock=None, contract=None)

    monkeypatch.setattr(stop_mod, "_wait_for_runtime_stop", server_exits)
    assert stop_mod.stop_runtime_from_dir(str(runtime_dir)) == 0
    assert not (logs / "aps_runtime.json").exists()
    assert not (configured_logs / "aps_runtime.json").exists()


def test_release_follows_the_database_lock_path_recorded_in_the_claim(tmp_path):
    """释放只认 claim：没有可核对的数据库锁时只放壳锁；数据库锁按 claim 记录的路径释放。"""
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "app" / "logs", tmp_path / "aps.db"
    claim = _acquire(runtime_dir, logs, database)
    database_lock = Path(db_scope_lock_path(str(database)))
    assert claim["db_lock"]["path"] == str(database_lock)
    shell = read_runtime_lock_result(str(logs)).payload
    assert stop_mod.release_initial_runtime_locks(str(logs), shell, None)
    assert not (logs / "aps_runtime.lock").exists() and database_lock.exists()
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=claim)
    assert not database_lock.exists()


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
        current_runtime_owner=lambda: _OWNER,
        resolve_prelaunch_log_dir=lambda runtime_dir: str(prelaunch_log_dir),
        acquire_runtime_lock=lock_mod.acquire_runtime_lock,
        release_runtime_lock=lock_mod.release_runtime_lock,
        delete_runtime_contract_files=lambda *a, **k: None,
        write_runtime_contract_file=lambda *a, **k: {"path": "", "payload": {}},
        default_chrome_profile_dir=lambda runtime_dir: str(tmp_path / "chrome-profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred_port, logger=None, state_dir=None, runtime_dir=None: (host, 6322),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: 0,
        serve_runtime_app=lambda app, host, port: events.append("serve"),
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        atexit_register=_atexit_register,
        install_run_runtime=install_workbench_run_runtime,
        resolve_startup_debug_flag=lambda: False,
        resolve_runtime_db_path=resolve_runtime_db_path,
        prepare_runtime_server=None,
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
    first = lock_mod.acquire_runtime_lock(
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

    lock_mod.release_runtime_lock(str(logs1), expected_payload=first)


def test_quality_gate_runtime_probe_does_not_let_stale_contract_mask_active_lock_or_endpoint(monkeypatch) -> None:
    import scripts.run_quality_gate as gate_mod

    stale_contract = {"pid": 1001, "exe_path": "/bin/stale-aps", "host": "127.0.0.1", "port": 6322}
    active_lock = {"pid": 2002, "exe_path": "/bin/live-aps"}
    paths = {"contract_path": "/tmp/aps_runtime.json", "lock_path": "/tmp/aps_runtime.lock"}

    monkeypatch.setattr(gate_mod, "_pid_state", lambda pid: pid == 2002)
    monkeypatch.setattr(gate_mod, "_pid_matches_contract", lambda pid, exe_path: pid == 2002)

    pid_state, pid, pid_match, exe_path = gate_mod._effective_pid_signal(stale_contract, active_lock)
    assert pid_state == "active"
    assert pid == 2002 and pid_match is True and exe_path == "/bin/live-aps"

    monkeypatch.setattr(gate_mod, "_load_runtime_state", lambda: (stale_contract, active_lock, paths))
    monkeypatch.setattr(
        gate_mod, "_health_signal", lambda contract: (gate_mod.RuntimeProbeState.STALE, "127.0.0.1", 6322)
    )
    with pytest.raises(RuntimeError, match="pid=2002"):
        gate_mod._assert_no_active_runtime()

    monkeypatch.setattr(gate_mod, "_load_runtime_state", lambda: (stale_contract, None, paths))
    monkeypatch.setattr(
        gate_mod, "_health_signal", lambda contract: (gate_mod.RuntimeProbeState.ACTIVE, "127.0.0.1", 6322)
    )
    with pytest.raises(RuntimeError, match="pid_state=stale health_state=active"):
        gate_mod._assert_no_active_runtime()

