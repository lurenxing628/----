"""同库多实例冲突在启动触库前被拒绝。"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
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
from web.bootstrap.workbench_run_lifecycle import release_runtime_after_jobs
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
        assert (lock_mod.read_runtime_lock_result_from_path(str(database_lock)).payload or {})["owner"] == "stale-owner"
        resume.set()
        assert installed.wait(10)
        state, payload = results.get(timeout=3)
        assert state == "acquired", payload
        assert payload["pid"] == first.pid
        assert (lock_mod.read_runtime_lock_result_from_path(str(database_lock)).payload or {})["pid"] == first.pid
        assert (read_runtime_lock_result(str(logs1)).payload or {})["pid"] == first.pid
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
    assert (contracts_mod.read_runtime_contract_result(str(mirror)).payload or {})["instance_id"] == "new-mirror-instance"
    assert not (logs / "aps_runtime.json").exists()
    assert (logs / "aps_runtime.lock").is_file()
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=old_lock)

    new_lock = _acquire(runtime_dir, logs, database)
    publication = _publish_claim(runtime_dir, logs, database, new_lock, "new-primary-instance")
    saved = Path(publication["path"]).read_bytes()
    result = cleanup_mod.delete_runtime_contract_files_result(str(logs), expected_lock=old_lock, expected_contract=old_contract)
    assert not result.ok and any(failure.reason == "ownership_changed" for failure in result.failures)
    assert Path(publication["path"]).read_bytes() == saved
    assert (read_runtime_lock_result(str(logs)).payload or {})["started_at"] == new_lock["started_at"]
    assert (lock_mod.read_runtime_lock_result_from_path(db_scope_lock_path(str(database))).payload or {})["started_at"] == new_lock["db_lock"]["started_at"]
    assert not lock_mod.release_runtime_lock(str(logs), expected_payload=old_lock)
    assert lock_mod.release_runtime_lock(str(logs), expected_payload=new_lock)


def test_shutdown_release_uses_original_three_identities_and_cleans_log_mirror(tmp_path, monkeypatch):
    """停机 finally 的 release_runtime_after_jobs 按原锁、原 db 锁、原契约三份身份删契约（含配置日志镜像）并释锁。"""
    _distinct_lock_starts(monkeypatch)
    runtime_dir, logs, database = tmp_path / "app", tmp_path / "app" / "logs", tmp_path / "aps.db"
    configured_logs = tmp_path / "configured-logs"
    state: Dict[str, Any] = {}

    deps = replace(entrypoint_mod._default_deps("default"), resolve_runtime_db_path=lambda directory: str(database))
    assert entrypoint_mod._acquire_runtime_lock_before_app(
        deps, runtime_dir=str(runtime_dir), lock_scope_target=str(runtime_dir), lock_scope_log_dir=None,
        runtime_owner=_OWNER, prelaunch_log_dir=str(logs), runtime_lock_state=state,
    ) is None
    app = Flask("original-exit")
    app.config.update(LOG_DIR=str(configured_logs), DATABASE_PATH=str(database), BACKUP_DIR=str(runtime_dir / "backups"),
                      EXCEL_TEMPLATE_DIR=str(runtime_dir / "templates"), APP_UI_MODE="new_ui")
    assert entrypoint_mod._publish_runtime_contract(
        deps, app, runtime_dir=str(runtime_dir), host="127.0.0.1", port=6322,
        runtime_owner=_OWNER, lock_state=state,
    ) is None
    assert state["contract_cleanup_dir"] == str(logs)
    assert state["contract"]["data_dirs"]["log_dir"] == str(configured_logs)
    for filename in ("aps_runtime.json", "aps_host.txt", "aps_port.txt", "aps_db_path.txt"):
        assert (logs / filename).read_bytes() == (configured_logs / filename).read_bytes()
    assert len({state["payload"]["started_at"], state["payload"]["db_lock"]["started_at"], state["contract"]["started_at"]}) == 3

    release_runtime_after_jobs(deps, state, str(runtime_dir))
    assert not (logs / "aps_runtime.lock").exists() and not Path(db_scope_lock_path(str(database))).exists()
    assert not (logs / "aps_runtime.json").exists()
    assert not (configured_logs / "aps_runtime.json").exists()

    repeated = cleanup_mod.delete_runtime_contract_files_result(
        str(logs), expected_lock=state["payload"], expected_contract=state["contract"],
    )
    assert repeated.ok, "服务退出已删除镜像契约，停止命令重复清理应成功"


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
    assert (contracts_mod.read_runtime_contract_result(str(logs)).payload or {})["instance_id"] == "new-stop-instance"
    assert (read_runtime_lock_result(str(logs)).payload or {})["started_at"] == new["lock"]["started_at"]
    assert (lock_mod.read_runtime_lock_result_from_path(db_scope_lock_path(str(database))).payload or {})["started_at"] == new["lock"]["db_lock"]["started_at"]
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


def _make_real_lock_deps(tmp_path: Path, events: List[str], *, prelaunch_log_dir: Path) -> EntryPointDeps:
    def _create_app() -> Flask:
        events.append("create_app")
        app = Flask("db-scope-lock-entrypoint-test")
        app.config["LOG_DIR"] = str(prelaunch_log_dir)
        return app

    class _StubServer:
        server_address = ("127.0.0.1", 6322)

        def shutdown(self) -> None:
            events.append("server_shutdown")

        def server_close(self) -> None:
            events.append("server_close")

    return EntryPointDeps(
        create_app=_create_app,
        clear_launch_error=lambda *a, **k: None,
        current_runtime_owner=lambda: _OWNER,
        resolve_prelaunch_log_dir=lambda runtime_dir: str(prelaunch_log_dir),
        acquire_runtime_lock=lock_mod.acquire_runtime_lock,
        release_runtime_lock=lock_mod.release_runtime_lock,
        delete_runtime_contract_files=cleanup_mod.delete_runtime_contract_files_result,
        write_runtime_contract_file=lambda *a, **k: {"path": "", "payload": {}},
        default_chrome_profile_dir=lambda runtime_dir: str(tmp_path / "chrome-profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: 0,
        serve_runtime_app=lambda *, server: events.append("serve"),
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        install_run_runtime=install_workbench_run_runtime,
        resolve_startup_debug_flag=lambda: False,
        resolve_runtime_db_path=resolve_runtime_db_path,
        prepare_runtime_server=lambda app, host, preferred_port: _StubServer(),
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
    deps = _make_real_lock_deps(tmp_path, events, prelaunch_log_dir=tmp_path / "inst2-prelaunch")

    rc = entrypoint_mod.app_main(anchor_file=str(inst2_dir / "app.py"), argv=[], deps=deps)

    assert rc == 13, "同库第二实例必须以锁失败返回码退出"
    assert "create_app" not in events, "被拒的第二实例绝不许执行 create_app（含迁移/退出备份注册）"
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


@pytest.fixture
def restore_signal_handlers(monkeypatch):
    """开发重载路径会替换 SIGTERM 处理器；pytest 进程还要继续跑，用例结束后还原原处理器。"""
    real_signal = signal.signal
    originals: Dict[int, Any] = {}

    def _tracked_signal(signum, handler):
        previous = real_signal(signum, handler)
        originals.setdefault(signum, previous)
        return previous

    monkeypatch.setattr(signal, "signal", _tracked_signal)
    yield
    for signum, handler in originals.items():
        real_signal(signum, handler)


@pytest.mark.usefixtures("restore_signal_handlers")
def test_reloader_parent_process_only_supervises_without_runtime_side_effects(tmp_path: Path, monkeypatch) -> None:
    """U15-1: 开发重载父进程（DEBUG=True 且无 WERKZEUG_RUN_MAIN）只进入 reloader 监督，
    触库、写秘密、注册备份、拿锁、创建 server 全为 0 次。"""
    import werkzeug._reloader as reloader_mod

    from web.bootstrap import factory as factory_mod

    runtime_dir = tmp_path / "parent-app"
    runtime_dir.mkdir()
    db_path = tmp_path / "parent-db" / "aps.db"
    log_dir = tmp_path / "parent-logs"
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    reloader_calls: List[str] = []
    side_effects: List[str] = []

    class _FakeParentReloader:
        def restart_with_reloader(self) -> int:
            reloader_calls.append("restart_with_reloader")
            return 0

    monkeypatch.setitem(reloader_mod.reloader_loops, "auto", _FakeParentReloader)

    deps = replace(
        entrypoint_mod._default_deps("default"),
        resolve_startup_debug_flag=lambda: True,
        clear_launch_error=lambda *a, **k: side_effects.append("clear_launch_error"),
        acquire_runtime_lock=lambda *a, **k: side_effects.append("acquire_lock"),
        create_app=lambda: side_effects.append("create_app"),  # type: ignore[arg-type,return-value]
        prepare_runtime_server=lambda *a, **k: side_effects.append("prepare_server"),
        serve_runtime_app=lambda *, server: side_effects.append("serve"),
    )

    rc = entrypoint_mod.app_main(anchor_file=str(runtime_dir / "app.py"), argv=[], deps=deps)
    assert rc == 0
    assert reloader_calls == ["restart_with_reloader"]
    assert side_effects == []
    assert not db_path.exists()
    assert not (log_dir / "aps_secret_key.txt").exists()
    assert not (runtime_dir / "logs" / "aps_runtime.lock").exists()
    assert factory_mod._EXIT_BACKUP_REGISTERED is False


@pytest.mark.usefixtures("restore_signal_handlers")
def test_reloader_second_child_lock_conflict_exits_13_before_create_app_and_parent_propagates_13(
    tmp_path: Path, monkeypatch
) -> None:
    """U15-2: 第二实例开发重载父进程拉起子进程（WERKZEUG_RUN_MAIN=true），
    子进程在 create_app 前因锁冲突以 rc=13 退出，父进程原样返回 13。"""
    import werkzeug._reloader as reloader_mod

    db = tmp_path / "shared" / "db" / "aps.db"
    monkeypatch.setenv("APS_DB_PATH", str(db))
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

    logs1 = tmp_path / "inst1-logs"
    first = lock_mod.acquire_runtime_lock(
        str(tmp_path / "inst1"),
        str(logs1),
        owner=_OWNER,
        exe_path=sys.executable,
        db_path=str(db),
    )

    inst2_dir = tmp_path / "inst2"
    inst2_dir.mkdir()
    events: List[str] = []
    base_deps = _make_real_lock_deps(tmp_path, events, prelaunch_log_dir=tmp_path / "inst2-prelaunch")
    deps = replace(
        base_deps,
        resolve_startup_debug_flag=lambda: True,
        should_use_runtime_reloader=lambda debug: True,
        should_own_runtime_resources=entrypoint_mod.should_own_runtime_resources,
    )

    child_attempts: List[int] = []

    class _LoopReloader:
        def restart_with_reloader(self) -> int:
            while True:
                monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
                code = entrypoint_mod.app_main(anchor_file=str(inst2_dir / "app.py"), argv=[], deps=deps)
                child_attempts.append(code)
                if code != 3:
                    return code

    monkeypatch.setitem(reloader_mod.reloader_loops, "auto", _LoopReloader)
    try:
        rc = entrypoint_mod.app_main(anchor_file=str(inst2_dir / "app.py"), argv=[], deps=deps)
        assert rc == 13
        assert child_attempts == [13]
        assert "create_app" not in events
    finally:
        lock_mod.release_runtime_lock(str(logs1), expected_payload=first)


def test_recovery_host_disables_runtime_reloader_even_in_debug_child(tmp_path: Path, monkeypatch) -> None:
    """U15-4: 恢复宿主（WORKBENCH_RUN_RUNTIME_REASON == RECOVERY）在 DEBUG=True 子进程中也强制禁用重载。"""
    import werkzeug._reloader as reloader_mod

    from web.bootstrap.workbench_system_restore_recovery import RECOVERY, configure_system_restore_recovery

    runtime_dir = tmp_path / "recovery-app"
    runtime_dir.mkdir()
    db_path = tmp_path / "recovery-db" / "aps.db"
    db_path.parent.mkdir()
    log_dir = runtime_dir / "logs"
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")

    app = Flask("recovery-host-no-reloader")
    app.config.update(
        DEBUG=True,
        DATABASE_PATH=str(db_path),
        LOG_DIR=str(log_dir),
        BACKUP_DIR=str(runtime_dir / "backups"),
        EXCEL_TEMPLATE_DIR=str(runtime_dir / "templates"),
        APP_UI_MODE="default",
        WORKBENCH_SYSTEM_JOURNAL_DIR=str(tmp_path / "journal"),
    )
    configure_system_restore_recovery(app)
    assert app.config.get("WORKBENCH_RUN_RUNTIME_REASON") == RECOVERY

    reloader_constructed: List[str] = []
    served: List[str] = []

    class _ForbiddenReloader:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            reloader_constructed.append("reloader_init")

    monkeypatch.setitem(reloader_mod.reloader_loops, "auto", _ForbiddenReloader)

    class _StubServer:
        def __init__(self, host: str, preferred_port: int) -> None:
            self.host = host
            self.port = 6329
            self.preferred_port = preferred_port
            self.server_address = (host, self.port)

        def shutdown(self) -> None:
            served.append("shutdown")

        def server_close(self) -> None:
            served.append("server_close")

    deps = replace(
        entrypoint_mod._default_deps("default"),
        create_app=lambda: app,
        resolve_startup_debug_flag=lambda: True,
        should_use_runtime_reloader=lambda debug: True,
        should_own_runtime_resources=lambda debug: True,
        prepare_runtime_server=lambda target_app, host, preferred_port: _StubServer(host, preferred_port),
        serve_runtime_app=lambda *, server: served.append(f"serve:{server.host}:{server.port}"),
    )

    rc = entrypoint_mod.app_main(anchor_file=str(runtime_dir / "app.py"), argv=[], deps=deps)
    assert rc == 0
    assert reloader_constructed == [], "恢复宿主必须强制禁用 reloader"
    assert served == ["serve:127.0.0.1:6329", "server_close"]
    assert not (log_dir / "aps_runtime.lock").exists()
    assert not Path(db_scope_lock_path(str(db_path))).exists()


@pytest.mark.usefixtures("restore_signal_handlers")
def test_reloader_child_file_change_triggers_ordered_cleanup_and_exit_3_then_normal_shutdown_exits_0(
    tmp_path: Path, monkeypatch, request
) -> None:
    """U15-5: 真实文件修改触发重载（返回 3，并严格按序完成关闭 server → 排空 → 备份 → 删契约 → 释锁），
    随后新子进程按回写的契约端口重绑（POSIX 上即原 TIME_WAIT 端口），并在 SIGTERM 停机时返回 0。"""
    import threading
    import time
    import urllib.request

    import werkzeug._reloader as reloader_mod

    from web.bootstrap import factory as factory_mod
    from web.bootstrap import runtime_server as runtime_server_mod

    runtime_dir = tmp_path / "reloader-app"
    runtime_dir.mkdir()
    db_path = tmp_path / "reloader-db" / "aps.db"
    db_path.parent.mkdir()
    log_dir = runtime_dir / "logs"
    watched_file = tmp_path / "watched_target.py"
    watched_file.write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    monkeypatch.delenv("APS_HOST", raising=False)
    monkeypatch.setenv("APS_PORT", "0")
    monkeypatch.setattr(
        runtime_server_mod,
        "candidate_ports",
        lambda preferred: [preferred] if preferred > 0 else [],
    )

    monkeypatch.setattr(
        reloader_mod,
        "_find_stat_paths",
        lambda extra_files, exclude_patterns: [str(watched_file)],
    )
    stop_watchers = threading.Event()
    request.addfinalizer(stop_watchers.set)

    class _StoppableStatReloader(reloader_mod.StatReloaderLoop):
        # SIGTERM 停机后监视线程不会自行退出；用例结束时让它以非 3 退出码收尾，不在 pytest 进程里空转。
        def run_step(self) -> None:
            if stop_watchers.is_set():
                raise SystemExit(0)
            super().run_step()

    monkeypatch.setitem(
        reloader_mod.reloader_loops,
        "auto",
        lambda *a, **k: _StoppableStatReloader(interval=0.02),
    )

    order: List[str] = []
    bound_ports: List[int] = []
    contract_ports: List[int] = []
    server_ready = threading.Event()

    class _TrackedRuntime:
        ready = True
        stopped = False

        def __init__(self, target_db: str) -> None:
            self.db_path = target_db

        class proof:
            @staticmethod
            def verify() -> None:
                return None

        @staticmethod
        def shutdown(wait: bool = True) -> bool:
            if not _TrackedRuntime.stopped:
                _TrackedRuntime.stopped = True
                order.append("drain_runtime")
            return True

    monkeypatch.setattr(factory_mod, "_run_exit_backup", lambda: (order.append("exit_backup"), True)[1])
    monkeypatch.setattr(
        "web.bootstrap.workbench_system_restore.install_workbench_system_restore_host",
        lambda target_app, runtime: None,
    )

    def _prepare_and_track(target_app: Flask, host: str, preferred_port: int):
        server = runtime_server_mod.prepare_runtime_server(target_app, host, preferred_port)
        bound_ports.append(int(server.server_address[1]))
        original_serve_forever = server.serve_forever
        original_close = server.server_close

        def _tracked_serve_forever(*a: Any, **k: Any) -> None:
            server_ready.set()
            original_serve_forever(*a, **k)

        def _tracked_close() -> None:
            if "server_close" not in order:
                order.append("server_close")
            original_close()

        server.serve_forever = _tracked_serve_forever  # type: ignore[method-assign]
        server.server_close = _tracked_close  # type: ignore[method-assign]
        return server

    def _delete_contracts(directory: str, **kwargs: Any):
        order.append("delete_contract")
        return cleanup_mod.delete_runtime_contract_files_result(directory, **kwargs)

    def _release_lock(scope: str, **kwargs: Any) -> bool:
        order.append("release_lock")
        return lock_mod.release_runtime_lock(scope, **kwargs)

    def _write_contract(directory: str, host: str, port: int, **kwargs: Any):
        contract_ports.append(int(port))
        return contracts_mod.write_runtime_contract_file(directory, host, port, **kwargs)

    def _make_app() -> Flask:
        app = Flask("reloader-cycle-test")
        app.config.update(
            DEBUG=True,
            DATABASE_PATH=str(db_path),
            LOG_DIR=str(log_dir),
            BACKUP_DIR=str(runtime_dir / "backups"),
            EXCEL_TEMPLATE_DIR=str(runtime_dir / "templates"),
            APP_UI_MODE="default",
        )
        app.extensions["workbench_startup_maintenance_records"] = ()

        @app.get("/ping")
        def _ping() -> str:
            return "pong"

        return app

    deps = replace(
        entrypoint_mod._default_deps("default"),
        create_app=_make_app,
        install_run_runtime=lambda target_app, runtime_lock: _TrackedRuntime(str(db_path)),
        prepare_runtime_server=_prepare_and_track,
        serve_runtime_app=factory_mod.serve_runtime_app,
        delete_runtime_contract_files=_delete_contracts,
        release_runtime_lock=_release_lock,
        write_runtime_contract_file=_write_contract,
        resolve_startup_debug_flag=lambda: True,
        should_use_runtime_reloader=lambda debug: True,
        should_own_runtime_resources=lambda debug: True,
    )

    # 第一轮：先发起带 Connection: close 的真实 HTTP 请求使原端口产生 TIME_WAIT，再修改文件触发重载 -> 返回 3
    def _modify_watched_file() -> None:
        assert server_ready.wait(timeout=5)
        req = urllib.request.Request(
            f"http://127.0.0.1:{bound_ports[0]}/ping",
            headers={"Connection": "close"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.read() == b"pong"
        time.sleep(0.05)
        watched_file.write_text("VALUE = 2\n", encoding="utf-8")
        now = time.time() + 2.0
        os.utime(watched_file, (now, now))

    modifier = threading.Thread(target=_modify_watched_file, daemon=True)
    modifier.start()
    rc1 = entrypoint_mod.app_main(anchor_file=str(runtime_dir / "app.py"), argv=[], deps=deps)
    modifier.join(timeout=5)
    assert rc1 == 3
    assert order == [
        "server_close",
        "drain_runtime",
        "exit_backup",
        "delete_contract",
        "release_lock",
    ]
    assert not (log_dir / "aps_runtime.json").exists()
    assert not (log_dir / "aps_runtime.lock").exists()
    assert not Path(db_scope_lock_path(str(db_path))).exists()

    # 第二轮：重载后的新子进程按回写的 APS_PORT 重绑，并通过 SIGTERM 触发正常关停 -> 返回 0。
    # raise_signal 只投递本进程已装的处理器；os.kill(SIGTERM) 在 Windows 上会直接结束整个 pytest 进程。
    order.clear()
    server_ready.clear()
    _TrackedRuntime.stopped = False

    def _trigger_sigterm_shutdown() -> None:
        assert server_ready.wait(timeout=5)
        req = urllib.request.Request(
            f"http://127.0.0.1:{bound_ports[1]}/ping",
            headers={"Connection": "close"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.read() == b"pong"
        signal.raise_signal(signal.SIGTERM)

    stopper = threading.Thread(target=_trigger_sigterm_shutdown, daemon=True)
    stopper.start()
    rc2 = entrypoint_mod.app_main(anchor_file=str(runtime_dir / "app.py"), argv=[], deps=deps)
    stopper.join(timeout=5)
    assert rc2 == 0
    assert len(bound_ports) == 2 and contract_ports == bound_ports, "契约端口必须等于实际监听端口"
    if os.name != "nt":
        # Windows 独占监听（SO_EXCLUSIVEADDRUSE）下 TIME_WAIT 端口可能拒绝重绑并回退到新端口。
        assert bound_ports[1] == bound_ports[0]
    assert order == [
        "server_close",
        "drain_runtime",
        "exit_backup",
        "delete_contract",
        "release_lock",
    ]
    assert not (log_dir / "aps_runtime.json").exists()
    assert not (log_dir / "aps_runtime.lock").exists()
    assert not Path(db_scope_lock_path(str(db_path))).exists()


def test_invalid_or_above_dword_lock_pid_fails_closed_without_deleting_lock_files(tmp_path: Path) -> None:
    db = tmp_path / "shared" / "aps.db"
    db.parent.mkdir(parents=True)
    logs = tmp_path / "inst-logs"
    logs.mkdir(parents=True)
    shell_lock = logs / "aps_runtime.lock"
    db_lock = Path(db_scope_lock_path(str(db)))

    for bad_pid in ("4294967296", "１２３４", "0123", "0", "9" * 6000):
        raw_lock = (
            f"pid={bad_pid}\n"
            f"owner={_OWNER}\n"
            f"exe_path={sys.executable}\n"
            "started_at=2026-01-01T00:00:00Z\n"
            f"db_path={db}\n"
        ).encode()
        shell_lock.write_bytes(raw_lock)
        parsed = read_runtime_lock_result(str(logs))
        assert parsed.status == "invalid" and parsed.reason == "invalid_pid" and parsed.payload is None

        with pytest.raises(lock_mod.RuntimeLockError):
            _acquire(tmp_path / "inst", logs, db)
        assert shell_lock.read_bytes() == raw_lock, f"异常锁 pid={bad_pid[:16]!r} 绝不得按不存在进程误删"
        assert not db_lock.exists()

    shell_lock.unlink()
    db_lock_bytes = (
        "pid=4294967296\n"
        f"owner={_OWNER}\n"
        f"exe_path={sys.executable}\n"
        "started_at=2026-01-01T00:00:00Z\n"
        f"db_path={db}\n"
    ).encode()
    db_lock.write_bytes(db_lock_bytes)
    with pytest.raises(lock_mod.RuntimeLockError):
        _acquire(tmp_path / "inst", logs, db)
    assert db_lock.read_bytes() == db_lock_bytes
    assert not shell_lock.exists()


def test_diverged_lock_namespace_shared_db_missing_exe_path_blocks_live_pid_and_replaces_dead_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "shared" / "db" / "aps.db"
    db.parent.mkdir(parents=True)
    db_lock = Path(db_scope_lock_path(str(db)))
    inst1 = tmp_path / "inst1"
    logs1 = tmp_path / "inst1-logs"
    exe_a = str(inst1 / "APS.exe")
    inst2 = tmp_path / "inst2"
    logs2 = tmp_path / "inst2-logs"
    exe_b = str(inst2 / "APS.exe")

    # 活 PID（实例 A）获取双锁后，抹掉共享 db_lock 中的 exe_path= 行：
    # 实例 B 以不同 exe_b 启动时，绝不能把 exe_b 当被探针进程的预期身份，必须按活跃锁阻断并回滚 B 壳锁
    lock_mod.acquire_runtime_lock(
        str(inst1),
        str(logs1),
        owner="owner-a",
        exe_path=exe_a,
        db_path=str(db),
    )
    db_lock.write_text(
        "".join(
            line
            for line in db_lock.read_text(encoding="utf-8").splitlines(keepends=True)
            if not line.startswith("exe_path=")
        ),
        encoding="utf-8",
    )

    with pytest.raises(lock_mod.RuntimeLockError, match="owner-a"):
        lock_mod.acquire_runtime_lock(
            str(inst2),
            str(logs2),
            owner="owner-b",
            exe_path=exe_b,
            db_path=str(db),
        )
    assert not (logs2 / "aps_runtime.lock").exists(), "db 锁阻断后必须回滚本实例壳锁"
    assert (lock_mod.read_runtime_lock_result_from_path(str(db_lock)).payload or {})["owner"] == "owner-a"

    with monkeypatch.context() as mp:
        mp.setattr(lock_mod.launcher_win32, "available", lambda: True)
        mp.setattr(lock_mod.launcher_win32, "pid_exists", lambda _pid: True)
        mp.setattr(lock_mod.launcher_win32, "executable_path", lambda _pid: exe_a)
        mp.setattr(
            lock_mod,
            "is_runtime_lock_active",
            lambda payload, expected_exe_path="", *, local_probe_only=False: lock_mod._native_runtime_lock_active(
                payload["pid"],
                payload,
                expected_exe_path,
            ),
        )
        with pytest.raises(lock_mod.RuntimeLockError, match="owner-a"):
            lock_mod.acquire_runtime_lock(
                str(inst2),
                str(logs2),
                owner="owner-b",
                exe_path=exe_b,
                db_path=str(db),
            )
        assert not (logs2 / "aps_runtime.lock").exists(), "Windows 原生探针下 db 锁阻断后同样必须回滚壳锁"
        assert (lock_mod.read_runtime_lock_result_from_path(str(db_lock)).payload or {})["owner"] == "owner-a"

    (logs1 / "aps_runtime.lock").unlink()
    db_lock.unlink()

    # 死 PID 且锁文件缺失 exe_path：仍按陈旧锁清理并由新实例 B 接管
    dead_no_exe = dict(
        pid=99999999,
        owner="dead-owner",
        exe_path="",
        started_at="2000-01-01T00:00:00Z",
        db_path=str(db),
    )
    with lock_mod.runtime_lock_mutation_guard(str(db_lock)):
        assert lock_mod._create_new_runtime_lock(str(db_lock), dead_no_exe)

    claim_b = lock_mod.acquire_runtime_lock(
        str(inst2),
        str(logs2),
        owner="owner-b",
        exe_path=exe_b,
        db_path=str(db),
    )
    try:
        assert claim_b["pid"] == os.getpid()
        assert (lock_mod.read_runtime_lock_result_from_path(str(db_lock)).payload or {})["owner"] == "owner-b"
    finally:
        assert lock_mod.release_runtime_lock(str(logs2), expected_payload=claim_b)

