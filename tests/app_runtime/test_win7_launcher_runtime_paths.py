"""回归测试：Win7 启动器运行时路径/锁/契约/停止流程——共享数据根与各数据目录解析（含 frozen/注册表/环境变量）、运行时所有者与 Chrome 配置目录、运行时锁的失败即关闭（空/非法/不可读锁不被清理），以及 stop_runtime_from_dir 在端点存活、契约不可读/非法、端点文件不全或不可信、Chrome 清理未确认时保留产物并返回 busy，仅在确认停止后才清理（兜底 PID 强杀仅在 PID 确认匹配且契约有效时允许）；另守护 Chrome --user-data-dir 配置目录参数的精确匹配（拒绝相邻同名 profile）。"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import List

import pytest
from flask import Flask

from tests._support.paths import REPO_ROOT, REPO_ROOT_STR


def _repo_root() -> str:
    return REPO_ROOT_STR


def _import_launcher():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher", None)
    return importlib.import_module("web.bootstrap.launcher")


def _import_launcher_stop():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_stop", None)
    return importlib.import_module("web.bootstrap.launcher_stop")


def _import_launcher_stop_cleanup():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_stop_cleanup", None)
    return importlib.import_module("web.bootstrap.launcher_stop_cleanup")


def _import_launcher_cleanup_result():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_cleanup_result", None)
    return importlib.import_module("web.bootstrap.launcher_cleanup_result")


def _import_launcher_processes():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_processes", None)
    return importlib.import_module("web.bootstrap.launcher_processes")


def _import_launcher_lock_result():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module("web.bootstrap.launcher_lock_result")


def _import_factory():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.factory", None)
    return importlib.import_module("web.bootstrap.factory")


def _import_paths():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.paths", None)
    return importlib.import_module("web.bootstrap.paths")


def _import_launcher_paths():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_paths", None)
    return importlib.import_module("web.bootstrap.launcher_paths")


def test_runtime_base_dir_fallback_logs_to_stderr(monkeypatch, capsys):
    paths_mod = _import_paths()
    original_resolve = paths_mod.Path.resolve

    def _boom_resolve(self):
        raise RuntimeError("resolve boom")

    monkeypatch.setattr(paths_mod.Path, "resolve", _boom_resolve)
    got = paths_mod.runtime_base_dir(anchor_file=str(Path("C:/demo/app.py")))
    assert got.endswith(os.path.join("demo"))
    assert "运行根目录解析失败" in capsys.readouterr().err
    monkeypatch.setattr(paths_mod.Path, "resolve", original_resolve)


def test_resolve_shared_data_root_prefers_explicit_env(monkeypatch, tmp_path):
    launcher = _import_launcher()
    shared_root = tmp_path / "shared-data"
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    got = launcher.resolve_shared_data_root(str(tmp_path / "runtime"), frozen=False)
    assert got == os.path.abspath(str(shared_root))


def test_resolve_shared_data_root_uses_registry_only_when_frozen(monkeypatch, tmp_path):
    launcher = _import_launcher()
    base_dir = tmp_path / "app"
    registry_root = tmp_path / "registry-shared"
    monkeypatch.delenv("APS_SHARED_DATA_ROOT", raising=False)
    monkeypatch.setattr(launcher, "read_shared_data_root_from_registry", lambda: str(registry_root))
    got_dev = launcher.resolve_shared_data_root(str(base_dir), frozen=False)
    got_frozen = launcher.resolve_shared_data_root(str(base_dir), frozen=True)
    assert got_dev == os.path.abspath(str(base_dir))
    assert got_frozen == os.path.abspath(str(registry_root))


def test_resolve_prelaunch_log_dir_uses_shared_root(monkeypatch, tmp_path):
    launcher = _import_launcher()
    shared_root = tmp_path / "shared"
    monkeypatch.delenv("APS_LOG_DIR", raising=False)
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    got = launcher.resolve_prelaunch_log_dir(str(tmp_path / "runtime"), frozen=True)
    assert got == os.path.abspath(str(shared_root / "logs"))


def test_runtime_log_mirror_dir_disabled_when_frozen(monkeypatch, tmp_path):
    launcher_paths = _import_launcher_paths()
    runtime_dir = tmp_path / "Program Files" / "APS" / "SchedulerApp"
    shared_log_dir = tmp_path / "ProgramData" / "APS" / "shared-data" / "logs"

    monkeypatch.setattr(sys, "frozen", True, raising=False)

    got = launcher_paths.runtime_log_mirror_dir(str(runtime_dir), str(shared_log_dir))

    assert got == ""


def test_runtime_log_mirror_dir_keeps_dev_mirror_when_not_frozen(monkeypatch, tmp_path):
    launcher_paths = _import_launcher_paths()
    runtime_dir = tmp_path / "repo"
    shared_log_dir = tmp_path / "shared" / "logs"

    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert launcher_paths.runtime_log_mirror_dir(str(runtime_dir), str(shared_log_dir)) == os.path.abspath(str(runtime_dir / "logs"))


def test_apply_runtime_config_uses_shared_root_for_all_data_dirs(monkeypatch, tmp_path):
    factory = _import_factory()
    base_dir = tmp_path / "app"
    shared_root = tmp_path / "shared-data"
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    monkeypatch.delenv("APS_DB_PATH", raising=False)
    monkeypatch.delenv("APS_LOG_DIR", raising=False)
    monkeypatch.delenv("APS_BACKUP_DIR", raising=False)
    monkeypatch.delenv("APS_EXCEL_TEMPLATE_DIR", raising=False)
    app = Flask("aps-runtime-config-test")
    factory._apply_runtime_config(app, base_dir=str(base_dir))
    assert app.config["BASE_DIR"] == str(base_dir)
    assert app.config["DATABASE_PATH"] == os.path.join(os.path.abspath(str(shared_root)), "db", "aps.db")
    assert app.config["LOG_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "logs")
    assert app.config["BACKUP_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "backups")
    assert app.config["EXCEL_TEMPLATE_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "templates_excel")


def test_current_runtime_owner_uses_computername_when_userdomain_missing(monkeypatch):
    launcher = _import_launcher()
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.delenv("USERDOMAIN", raising=False)
    monkeypatch.setenv("COMPUTERNAME", "LOCALBOX")
    assert launcher.current_runtime_owner() == r"LOCALBOX\alice"


def test_default_chrome_profile_dir_prefers_localappdata_profile_name(monkeypatch, tmp_path):
    launcher = _import_launcher()
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\alice\AppData\Local")
    got = launcher.default_chrome_profile_dir(str(tmp_path))
    assert got == os.path.abspath(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile")


def test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir(tmp_path):
    launcher = _import_launcher()
    runtime_dir = tmp_path / "runtime-root"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)

    runtime_paths = launcher.resolve_runtime_state_paths(str(runtime_dir))
    log_paths = launcher.resolve_runtime_state_paths(str(state_dir))

    assert runtime_paths["runtime_dir"] == os.path.abspath(str(runtime_dir))
    assert log_paths["runtime_dir"] == os.path.abspath(str(runtime_dir))
    assert runtime_paths["state_dir"] == os.path.abspath(str(state_dir))
    assert log_paths["state_dir"] == os.path.abspath(str(state_dir))
    assert runtime_paths["contract_path"].endswith(os.path.join("logs", "aps_runtime.json"))
    assert log_paths["lock_path"].endswith(os.path.join("logs", "aps_runtime.lock"))


def _write_runtime_lock_file(state_dir: Path, pid: int) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "aps_runtime.lock"
    lock_path.write_text(
        f"pid={int(pid)}\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\n",
        encoding="utf-8",
    )
    return lock_path


def _assert_runtime_lock_error(callable_obj) -> None:
    try:
        callable_obj()
    except Exception as exc:
        if exc.__class__.__name__ == "RuntimeLockError":
            return
        raise
    raise AssertionError("应抛出 RuntimeLockError")


def test_read_runtime_lock_result_distinguishes_bad_lock_files(monkeypatch, tmp_path):
    launcher = _import_launcher()
    lock_mod = _import_launcher_lock_result()
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = state_dir / "aps_runtime.lock"

    assert launcher.read_runtime_lock_result(str(state_dir)).status == "missing"

    lock_path.write_text("", encoding="utf-8")
    empty = launcher.read_runtime_lock_result(str(state_dir))
    assert empty.status == "empty"
    assert launcher.read_runtime_lock(str(state_dir)) is None

    lock_path.write_text("owner=LOCALBOX\\alice\n", encoding="utf-8")
    missing_pid = launcher.read_runtime_lock_result(str(state_dir))
    assert missing_pid.status == "invalid"
    assert missing_pid.reason == "missing_pid"

    lock_path.write_text("pid=bad\nowner=LOCALBOX\\alice\n", encoding="utf-8")
    invalid_pid = launcher.read_runtime_lock_result(str(state_dir))
    assert invalid_pid.status == "invalid"
    assert invalid_pid.reason == "invalid_pid"

    real_read_fixed_text = lock_mod.read_fixed_text

    def _boom_read(path, *args, **kwargs):
        if str(path) == str(lock_path):
            raise PermissionError("denied")
        return real_read_fixed_text(path, *args, **kwargs)

    monkeypatch.setattr(lock_mod, "read_fixed_text", _boom_read)
    unreadable = launcher.read_runtime_lock_result(str(state_dir))
    assert unreadable.status == "unreadable"


def test_acquire_runtime_lock_fails_closed_for_empty_or_invalid_lock(tmp_path):
    launcher = _import_launcher()
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = state_dir / "aps_runtime.lock"

    lock_path.write_text("", encoding="utf-8")
    _assert_runtime_lock_error(lambda: launcher.acquire_runtime_lock(str(runtime_dir), str(state_dir)))
    assert lock_path.exists()

    lock_path.write_text("pid=bad\nowner=LOCALBOX\\alice\n", encoding="utf-8")
    _assert_runtime_lock_error(lambda: launcher.acquire_runtime_lock(str(runtime_dir), str(state_dir)))
    assert lock_path.exists()


def test_acquire_runtime_lock_fails_closed_when_lock_cannot_be_read(monkeypatch, tmp_path):
    launcher = _import_launcher()
    lock_mod = _import_launcher_lock_result()
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = _write_runtime_lock_file(state_dir, 12345)
    real_read_fixed_text = lock_mod.read_fixed_text

    def _boom_read(path, *args, **kwargs):
        if str(path) == str(lock_path):
            raise PermissionError("denied")
        return real_read_fixed_text(path, *args, **kwargs)

    monkeypatch.setattr(lock_mod, "read_fixed_text", _boom_read)

    _assert_runtime_lock_error(lambda: launcher.acquire_runtime_lock(str(runtime_dir), str(state_dir)))
    assert lock_path.exists()


def test_mixed_invalid_runtime_lock_is_not_cleaned_by_acquire_release_or_stop(tmp_path):
    launcher = _import_launcher()
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = state_dir / "aps_runtime.lock"
    lock_path.write_text(
        f"pid=999999\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\nBROKEN_LINE\n",
        encoding="utf-8",
    )

    result = launcher.read_runtime_lock_result(str(state_dir))
    assert result.status == "invalid"

    _assert_runtime_lock_error(lambda: launcher.acquire_runtime_lock(str(runtime_dir), str(state_dir)))
    assert lock_path.exists()

    launcher.release_runtime_lock(str(state_dir), expected_pid=999999)
    assert lock_path.exists()

    status = launcher._classify_runtime_state(str(state_dir))
    assert status["lock_status"] == "invalid"
    assert status["lock_active"] is True
    assert status["state"] == "mixed"
    assert launcher._runtime_stop_is_complete(status) is False
    assert lock_path.exists()


def test_release_runtime_lock_does_not_delete_when_expected_pid_invalid(tmp_path):
    launcher = _import_launcher()
    lock_path = _write_runtime_lock_file(tmp_path / "logs", 12345)

    launcher.release_runtime_lock(str(lock_path.parent), expected_pid="bad")  # type: ignore[arg-type]

    assert lock_path.exists()


def test_release_runtime_lock_does_not_delete_when_expected_pid_non_positive(tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "logs"

    lock_zero = _write_runtime_lock_file(state_dir, 12345)
    launcher.release_runtime_lock(str(state_dir), expected_pid=0)
    assert lock_zero.exists()

    lock_negative = _write_runtime_lock_file(state_dir, 12345)
    launcher.release_runtime_lock(str(state_dir), expected_pid=-1)
    assert lock_negative.exists()


def test_release_runtime_lock_only_deletes_matching_pid_or_current_process(tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "logs"

    mismatched = _write_runtime_lock_file(state_dir, 12345)
    launcher.release_runtime_lock(str(state_dir), expected_pid=54321)
    assert mismatched.exists()

    matched = _write_runtime_lock_file(state_dir, 12345)
    launcher.release_runtime_lock(str(state_dir), expected_pid=12345)
    assert not matched.exists()

    current = _write_runtime_lock_file(state_dir, os.getpid())
    launcher.release_runtime_lock(str(state_dir))
    assert not current.exists()


def _write_unreadable_runtime_contract_state(state_dir: Path, *, port: int = 5000) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "aps_runtime.json").write_text("{bad-json", encoding="utf-8")
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text(str(int(port)) + "\n", encoding="utf-8")


def _write_invalid_runtime_contract_state(state_dir: Path, payload) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "aps_runtime.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")


def _install_fast_stop_clock(monkeypatch, stop_mod, *, start: float = 1000.0):
    clock = {"now": float(start), "sleeps": []}

    monkeypatch.setattr(stop_mod.time, "time", lambda: clock["now"])

    def _sleep(seconds):
        sleep_for = max(float(seconds), 0.0)
        clock["sleeps"].append(sleep_for)
        clock["now"] += sleep_for

    monkeypatch.setattr(stop_mod.time, "sleep", _sleep)
    return clock


def test_stop_runtime_keeps_unreadable_contract_when_endpoint_still_healthy(monkeypatch, tmp_path):
    launcher = _import_launcher()
    _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "logs"
    _write_unreadable_runtime_contract_state(state_dir)
    calls = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: True)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert calls == {}
    assert (state_dir / "aps_runtime.json").exists()
    status = launcher._classify_runtime_state(str(state_dir))
    assert status["contract_status"] == "unreadable"
    assert status["state"] == "mixed"


def test_stop_runtime_keeps_unreadable_contract_when_endpoint_down(monkeypatch, tmp_path):
    launcher = _import_launcher()
    _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "logs"
    _write_unreadable_runtime_contract_state(state_dir)
    calls = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert calls == {}
    assert (state_dir / "aps_runtime.json").exists()
    assert (state_dir / "aps_host.txt").exists()
    assert (state_dir / "aps_port.txt").exists()
    status = launcher._classify_runtime_state(str(state_dir))
    assert status["contract_status"] == "unreadable"
    assert status["state"] == "blocked_contract"
    assert status["contract_reason"] != "contract_missing"


def test_stop_runtime_keeps_invalid_contract_when_endpoint_down(monkeypatch, tmp_path):
    launcher = _import_launcher()
    _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "logs"
    _write_invalid_runtime_contract_state(
        state_dir,
        {
            "contract_version": 2,
            "pid": 999999,
            "host": "127.0.0.1",
            "port": 5000,
            "shutdown_token": "token",
            "exe_path": sys.executable,
            "runtime_dir": str(tmp_path),
            "chrome_profile_dir": str(tmp_path / "profile"),
        },
    )
    calls = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert calls == {}
    assert (state_dir / "aps_runtime.json").exists()
    status = launcher._classify_runtime_state(str(state_dir))
    assert status["contract_status"] == "invalid"
    assert status["contract_reason"] == "contract_version_mismatch"
    assert status["state"] == "blocked_contract"
    assert launcher._runtime_stop_failure_reason(status, shutdown_requested=False) == "contract_invalid"
    assert launcher._runtime_stop_is_complete(status) is False


def test_stop_runtime_keeps_invalid_shape_contract_when_endpoint_down(monkeypatch, tmp_path):
    launcher = _import_launcher()
    _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "logs"
    _write_invalid_runtime_contract_state(state_dir, ["not", "dict"])
    calls = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert calls == {}
    assert (state_dir / "aps_runtime.json").exists()
    status = launcher._classify_runtime_state(str(state_dir))
    assert status["contract_status"] == "invalid"
    assert status["contract_reason"] == "contract_not_object"
    assert status["state"] == "blocked_contract"


def test_blocked_contract_state_is_not_stop_complete():
    launcher_stop = _import_launcher_stop()
    identity = {"contract_pid": 0, "pid_exists": False, "pid_match": None}

    state = launcher_stop._runtime_state_name(
        endpoint_up=False,
        contract=None,
        contract_status="unreadable",
        identity=identity,
        lock_active=False,
        has_artifacts=True,
    )

    assert state == "blocked_contract"
    assert launcher_stop._runtime_stop_is_complete({"state": state, "endpoint_up": False}) is False


def test_endpoint_down_with_confirmed_contract_pid_is_mixed_not_complete():
    launcher_stop = _import_launcher_stop()
    identity = {"contract_pid": 43210, "pid_exists": True, "pid_match": True}

    state = launcher_stop._runtime_state_name(
        endpoint_up=False,
        contract={"pid": 43210},
        contract_status="valid",
        identity=identity,
        lock_active=False,
        has_artifacts=True,
    )

    assert state == "mixed"
    assert launcher_stop._runtime_stop_is_complete({"state": state, "endpoint_up": False}) is False


def test_stop_runtime_keeps_artifacts_when_endpoint_files_unreadable(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    _install_fast_stop_clock(monkeypatch, launcher_stop)
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    host_path = state_dir / "aps_host.txt"
    port_path = state_dir / "aps_port.txt"
    host_path.write_text("127.0.0.1\n", encoding="utf-8")
    port_path.write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")
    calls = {}

    def _fake_endpoint_result(path: str):
        return launcher_stop.RuntimeEndpointReadResult(
            state_dir=os.path.abspath(path),
            host="",
            port=0,
            host_status="unreadable",
            port_status="missing",
            host_path=str(host_path),
            port_path=str(port_path),
            host_error="permission denied",
        )

    monkeypatch.setattr(launcher_stop, "read_runtime_endpoint_files_result", _fake_endpoint_result)
    monkeypatch.setattr(launcher_stop, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    assert launcher_stop.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert calls == {}
    assert host_path.exists()
    assert port_path.exists()
    assert (state_dir / "aps_db_path.txt").exists()
    status = launcher_stop._classify_runtime_state(str(state_dir))
    assert status["state"] == "blocked_endpoint"
    assert status["endpoint_host_status"] == "unreadable"
    assert status["endpoint_uncertain"] is True
    assert launcher_stop._runtime_stop_failure_reason(status, shutdown_requested=False) == "endpoint_files_uncertain"


def test_stop_runtime_keeps_artifacts_when_endpoint_port_invalid(monkeypatch, tmp_path):
    launcher = _import_launcher()
    _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("not-a-port\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert (state_dir / "aps_host.txt").exists()
    assert (state_dir / "aps_port.txt").exists()
    assert (state_dir / "aps_db_path.txt").exists()
    status = launcher._classify_runtime_state(str(state_dir))
    assert status["state"] == "blocked_endpoint"
    assert status["endpoint_port_status"] == "invalid"
    assert status["endpoint_uncertain"] is True


def test_stop_runtime_blocks_when_only_port_file_exists(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    _install_fast_stop_clock(monkeypatch, launcher_stop)
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    port_path = state_dir / "aps_port.txt"
    db_path = state_dir / "aps_db_path.txt"
    port_path.write_text("5000\n", encoding="utf-8")
    db_path.write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")

    def _health_down(host, port, state_dir):
        return launcher_stop.HealthProbeResult(False, f"http://{host}:{port}/system/health", "test_endpoint_down")

    monkeypatch.setattr(launcher_stop, "_health_result_for_status", _health_down)

    assert launcher_stop.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert port_path.exists()
    assert db_path.exists()
    status = launcher_stop._classify_runtime_state(str(state_dir))
    assert status["state"] == "blocked_endpoint"
    assert status["endpoint_host_status"] == "missing"
    assert status["endpoint_port_status"] == "valid"
    assert status["endpoint_uncertain"] is True


def test_stop_runtime_blocks_when_only_host_file_exists(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    _install_fast_stop_clock(monkeypatch, launcher_stop)
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    host_path = state_dir / "aps_host.txt"
    db_path = state_dir / "aps_db_path.txt"
    host_path.write_text("127.0.0.1\n", encoding="utf-8")
    db_path.write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")

    def _health_down(host, port, state_dir):
        return launcher_stop.HealthProbeResult(False, f"http://{host}:{port}/system/health", "test_endpoint_down")

    monkeypatch.setattr(launcher_stop, "_health_result_for_status", _health_down)

    assert launcher_stop.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert host_path.exists()
    assert db_path.exists()
    status = launcher_stop._classify_runtime_state(str(state_dir))
    assert status["state"] == "blocked_endpoint"
    assert status["endpoint_host_status"] == "valid"
    assert status["endpoint_port_status"] == "missing"
    assert status["endpoint_uncertain"] is True


def test_stop_runtime_blocks_when_host_file_blank_but_port_exists(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    _install_fast_stop_clock(monkeypatch, launcher_stop)
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    host_path = state_dir / "aps_host.txt"
    port_path = state_dir / "aps_port.txt"
    db_path = state_dir / "aps_db_path.txt"
    host_path.write_text("   \n", encoding="utf-8")
    port_path.write_text("5000\n", encoding="utf-8")
    db_path.write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")

    def _health_down(host, port, state_dir):
        return launcher_stop.HealthProbeResult(False, f"http://{host}:{port}/system/health", "test_endpoint_down")

    monkeypatch.setattr(launcher_stop, "_health_result_for_status", _health_down)

    assert launcher_stop.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 1
    assert host_path.exists()
    assert port_path.exists()
    assert db_path.exists()
    status = launcher_stop._classify_runtime_state(str(state_dir))
    assert status["state"] == "blocked_endpoint"
    assert status["endpoint_host_status"] == "empty"
    assert status["endpoint_port_status"] == "valid"
    assert status["endpoint_uncertain"] is True


def test_stop_runtime_still_cleans_stale_artifact_when_endpoint_files_missing(tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    db_path = state_dir / "aps_db_path.txt"
    db_path.write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")

    assert launcher.stop_runtime_from_dir(str(state_dir), timeout_s=0.1) == 0
    assert not db_path.exists()


def test_contract_endpoint_overrides_invalid_endpoint_file(tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("not-a-port\n", encoding="utf-8")
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path),
                "chrome_profile_dir": str(tmp_path / "profile"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = launcher._classify_runtime_state(str(state_dir))

    assert status["contract_status"] == "valid"
    assert status["host"] == "127.0.0.1"
    assert status["port"] == 5000
    assert status["endpoint_port_status"] == "invalid"
    assert status["endpoint_uncertain"] is False
    assert status["state"] != "blocked_endpoint"


def test_valid_contract_overrides_incomplete_endpoint_files(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5001,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path),
                "chrome_profile_dir": str(tmp_path / "profile"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _health_down(host, port, state_dir):
        return launcher_stop.HealthProbeResult(False, f"http://{host}:{port}/system/health", "test_endpoint_down")

    monkeypatch.setattr(launcher_stop, "_health_result_for_status", _health_down)
    status = launcher_stop._classify_runtime_state(str(state_dir))

    assert status["contract_status"] == "valid"
    assert status["host"] == "127.0.0.1"
    assert status["port"] == 5001
    assert status["endpoint_host_status"] == "missing"
    assert status["endpoint_port_status"] == "valid"
    assert status["endpoint_uncertain"] is False
    assert status["state"] != "blocked_endpoint"


def test_read_runtime_endpoint_files_legacy_shape(tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")

    got = launcher._read_runtime_endpoint_files(str(state_dir))

    assert got == {
        "host": "127.0.0.1",
        "port": 5000,
        "host_exists": True,
        "port_exists": True,
    }


def test_new_probe_runtime_health_result_monkeypatch_is_used(monkeypatch, tmp_path):
    launcher = _import_launcher()
    launcher_stop = _import_launcher_stop()
    state_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")
    (state_dir / "aps_launch_error.txt").write_text("old error\n", encoding="utf-8")

    def _fake_probe_result(host, port, timeout_s=1.5, *, log_failures=False, state_dir=None):
        return launcher_stop.HealthProbeResult(True, f"http://{host}:{port}/system/health")

    monkeypatch.setattr(launcher, "probe_runtime_health_result", _fake_probe_result)
    launcher._sync_launcher_hooks(include_chrome_hook=False)

    status = launcher._classify_runtime_state(str(state_dir))

    assert status["endpoint_up"] is True
    assert status["state"] == "active"


def test_legacy_read_runtime_lock_none_monkeypatch_is_respected(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    _write_runtime_lock_file(state_dir, 12345)

    monkeypatch.setattr(launcher_stop, "read_runtime_lock", lambda path: None)

    status = launcher_stop._classify_runtime_state(str(state_dir))

    assert status["lock_status"] == "missing"
    assert status["lock_active"] is False


def test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok(monkeypatch, tmp_path):
    launcher = _import_launcher()
    clock = _install_fast_stop_clock(monkeypatch, launcher._stop)
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    calls = {}
    waits = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: True)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))
    monkeypatch.setattr(
        launcher,
        "stop_aps_chrome_processes",
        lambda profile_dir, logger=None: calls.setdefault("chrome", profile_dir) or True,
    )

    def _wait_without_real_sleep(path, deadline):
        waits["state_dir"] = path
        waits["deadline"] = deadline
        return launcher._stop._classify_runtime_state(path)

    monkeypatch.setattr(launcher._stop, "_wait_for_runtime_stop", _wait_without_real_sleep)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert calls == {}
    assert waits["state_dir"] == os.path.abspath(str(state_dir))
    assert waits["deadline"] - clock["now"] == pytest.approx(12.0)


def test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    calls = {}

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)

    def _fake_delete(path: str) -> None:
        calls["delete"] = path

    def _fake_stop(profile_dir: str, logger=None) -> bool:
        calls["chrome"] = profile_dir
        return True

    monkeypatch.setattr(launcher, "delete_runtime_contract_files", _fake_delete)
    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", _fake_stop)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls["delete"] == os.path.abspath(str(state_dir))
    assert calls["chrome"] == os.path.abspath(str(tmp_path / "shared-data" / "chrome109_profile"))
    assert not (state_dir / "aps_host.txt").exists()
    assert not (state_dir / "aps_port.txt").exists()


def test_stop_runtime_legacy_cleanup_noop_still_cleans_files(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    custom_profile = tmp_path / "custom-profile"
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path / "shared-data"),
                "chrome_profile_dir": str(custom_profile),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls: List[str] = []

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.append(path))
    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", lambda profile_dir, logger=None: True)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls == [os.path.abspath(str(state_dir))]
    assert not (state_dir / "aps_runtime.json").exists()
    assert not (state_dir / "aps_host.txt").exists()
    assert not (state_dir / "aps_port.txt").exists()


def test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    custom_profile = tmp_path / "custom-profile"
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")
    (state_dir / "aps_launch_error.txt").write_text("old error\n", encoding="utf-8")
    (state_dir / "aps_runtime.lock").write_text(
        f"pid=999999\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\n",
        encoding="utf-8",
    )
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path / "shared-data"),
                "chrome_profile_dir": str(custom_profile),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = {}

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)

    def _fake_stop(profile_dir: str, logger=None) -> bool:
        calls["chrome"] = profile_dir
        return False

    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", _fake_stop)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert calls["chrome"] == os.path.abspath(str(custom_profile))
    assert (state_dir / "aps_runtime.json").exists()
    assert (state_dir / "aps_runtime.lock").exists()
    assert (state_dir / "aps_host.txt").exists()
    assert (state_dir / "aps_port.txt").exists()
    assert (state_dir / "aps_db_path.txt").exists()
    assert (state_dir / "aps_launch_error.txt").exists()


def test_stop_runtime_from_log_dir_cleans_files_after_chrome_cleanup_success(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    custom_profile = tmp_path / "custom-profile"
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")
    (state_dir / "aps_launch_error.txt").write_text("old error\n", encoding="utf-8")
    (state_dir / "aps_runtime.lock").write_text(
        f"pid=999999\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\n",
        encoding="utf-8",
    )
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path / "shared-data"),
                "chrome_profile_dir": str(custom_profile),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = []

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)

    def _fake_stop(profile_dir: str, logger=None) -> bool:
        calls.append(("chrome", profile_dir))
        return True

    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", _fake_stop)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls == [("chrome", os.path.abspath(str(custom_profile)))]
    assert not (state_dir / "aps_runtime.json").exists()
    assert not (state_dir / "aps_runtime.lock").exists()
    assert not (state_dir / "aps_host.txt").exists()
    assert not (state_dir / "aps_port.txt").exists()
    assert not (state_dir / "aps_db_path.txt").exists()
    assert not (state_dir / "aps_launch_error.txt").exists()


def test_stop_runtime_returns_failure_when_runtime_cleanup_fails(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    custom_profile = tmp_path / "custom-profile"
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_runtime.lock").write_text(
        f"pid=999999\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\n",
        encoding="utf-8",
    )
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path / "shared-data"),
                "chrome_profile_dir": str(custom_profile),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = []

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", lambda profile_dir, logger=None: calls.append(profile_dir) or True)

    def _cleanup_result(path: str):
        return launcher.RuntimeCleanupResult(
            state_dir=os.path.abspath(path),
            target_dirs=(os.path.abspath(path),),
            attempted_paths=(str(state_dir / "aps_runtime.json"),),
            removed_paths=(),
            missing_paths=(),
            failures=(
                launcher.RuntimeCleanupFailure(
                    path=str(state_dir / "aps_runtime.json"),
                    reason="remove_failed",
                    error="locked",
                ),
            ),
        )

    monkeypatch.setattr(launcher, "delete_runtime_contract_files_result", _cleanup_result)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert calls == [os.path.abspath(str(custom_profile))]
    assert (state_dir / "aps_runtime.json").exists()


def test_stop_runtime_retry_preserves_then_cleans_runtime_artifacts(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    custom_profile = tmp_path / "custom-profile"
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    (state_dir / "aps_db_path.txt").write_text(str(tmp_path / "db" / "aps.db") + "\n", encoding="utf-8")
    (state_dir / "aps_launch_error.txt").write_text("old error\n", encoding="utf-8")
    (state_dir / "aps_runtime.lock").write_text(
        f"pid=999999\nowner=LOCALBOX\\alice\nexe_path={sys.executable}\n",
        encoding="utf-8",
    )
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 999999,
                "host": "127.0.0.1",
                "port": 5000,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(tmp_path / "shared-data"),
                "chrome_profile_dir": str(custom_profile),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    stop_results = iter([False, True])

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", lambda profile_dir, logger=None: next(stop_results))

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert (state_dir / "aps_runtime.json").exists()
    assert (state_dir / "aps_runtime.lock").exists()
    assert (state_dir / "aps_host.txt").exists()
    assert (state_dir / "aps_port.txt").exists()
    assert (state_dir / "aps_db_path.txt").exists()
    assert (state_dir / "aps_launch_error.txt").exists()

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert not (state_dir / "aps_runtime.json").exists()
    assert not (state_dir / "aps_runtime.lock").exists()
    assert not (state_dir / "aps_host.txt").exists()
    assert not (state_dir / "aps_port.txt").exists()
    assert not (state_dir / "aps_db_path.txt").exists()
    assert not (state_dir / "aps_launch_error.txt").exists()


def test_stop_runtime_from_dir_waits_for_pid_exit_before_success(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    contract_path = state_dir / "aps_runtime.json"
    runtime_dir_json = str(tmp_path / "shared-data").replace("\\", "/")
    state_dir_json = str(state_dir).replace("\\", "/")
    contract_path.write_text(
        (
            "{\n"
            '  "contract_version": 1,\n'
            '  "pid": 43210,\n'
            '  "host": "127.0.0.1",\n'
            '  "port": 5000,\n'
            '  "exe_path": "D:/py3.8/python.exe",\n'
            '  "chrome_profile_dir": "C:/Temp/chrome-profile",\n'
            '  "shutdown_token": "runtime-stop-token",\n'
            f'  "runtime_dir": "{runtime_dir_json}",\n'
            f'  "data_dirs": {{"log_dir": "{state_dir_json}"}}\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    calls = {"pid_checks": 0}

    monkeypatch.setattr(launcher, "_request_runtime_shutdown", lambda contract, timeout_s=3.0: True)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=0.5: False)

    pid_states = iter([True, True, False])

    def _fake_pid_exists(pid: int) -> bool:
        calls["pid_checks"] += 1
        return next(pid_states)

    monkeypatch.setattr(launcher, "_pid_exists", _fake_pid_exists)
    monkeypatch.setattr(launcher, "_pid_state", lambda pid: _fake_pid_exists(pid))
    monkeypatch.setattr(launcher, "_pid_matches_contract", lambda pid, expected_exe_path: True)
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: calls.setdefault("kill", pid) or False)
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))
    monkeypatch.setattr(
        launcher,
        "stop_aps_chrome_processes",
        lambda profile_dir, logger=None: calls.setdefault("chrome", profile_dir) or True,
    )

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls["pid_checks"] >= 3
    assert calls["delete"] == os.path.abspath(str(state_dir))
    assert calls["chrome"] == "C:/Temp/chrome-profile"
    assert "kill" not in calls


def test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable(monkeypatch):
    launcher = _import_launcher()
    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: None)
    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is False


def test_windows_pid_state_unknown_when_tasklist_unavailable(monkeypatch, capsys):
    processes = _import_launcher_processes()
    monkeypatch.setattr(processes.os, "name", "nt")

    def _boom_run(*_args, **_kwargs):
        raise FileNotFoundError("tasklist missing")

    monkeypatch.setattr(processes.subprocess, "run", _boom_run)

    assert processes._pid_state(43210) is None
    assert processes._pid_exists(43210) is False
    assert "运行时身份状态未知" in capsys.readouterr().err


def test_stop_aps_chrome_processes_treats_already_gone_pid_as_success_after_final_recheck(monkeypatch):
    launcher = _import_launcher()
    pid_snapshots = iter([[100, 101], []])
    killed: List[int] = []

    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: next(pid_snapshots))
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: killed.append(int(pid)) or int(pid) == 100)

    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is True
    assert killed == [100, 101]


def test_stop_aps_chrome_processes_fails_when_final_recheck_still_finds_profile_process(monkeypatch):
    launcher = _import_launcher()
    pid_snapshots = iter([[100], [100]])

    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: next(pid_snapshots))
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: True)

    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is False


PROFILE_PREFIX = "--user-data-dir="


def _split_command_line_args(cmd: str) -> List[str]:
    tokens: List[str] = []
    buf: List[str] = []
    in_quotes = False
    cmd_text = str(cmd or "")
    for index, ch in enumerate(cmd_text):
        if ch == '"':
            slash_count = 0
            slash_index = index - 1
            while slash_index >= 0 and cmd_text[slash_index] == "\\":
                slash_count += 1
                slash_index -= 1
            if slash_count % 2 == 0:
                in_quotes = not in_quotes
                continue
        if not in_quotes and ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _command_line_matches_exact_profile(cmd: str, marker: str) -> bool:
    marker_lower = marker.lower()
    for arg in _split_command_line_args(cmd):
        arg_lower = arg.lower()
        if arg_lower.startswith(PROFILE_PREFIX) and arg_lower[len(PROFILE_PREFIX) :] == marker_lower:
            return True
    return False


def _command_line_matches_installer_profile(cmd: str, exact_marker: str, suffix_marker: str) -> bool:
    exact_lower = exact_marker.lower()
    suffix_lower = suffix_marker.lower()
    for arg in _split_command_line_args(cmd):
        arg_lower = arg.lower()
        if not arg_lower.startswith(PROFILE_PREFIX):
            continue
        profile = arg_lower[len(PROFILE_PREFIX) :]
        if exact_lower and profile == exact_lower:
            return True
        if suffix_lower and profile.endswith(suffix_lower):
            return True
    return False


def test_chrome_pid_query_script_matches_exact_user_data_dir_argument():
    launcher_stop = _import_launcher_stop()

    script = launcher_stop._chrome_pid_query_script(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile")

    assert "--user-data-dir=" in script
    assert "function Split-CommandLineArgs" in script
    assert "$slashCount" in script
    assert "[char]92" in script
    assert "$argLower.StartsWith($prefix)" in script
    assert "$argLower.Substring($prefix.Length) -eq $marker" in script
    assert "$cmd -match $profilePattern" not in script
    assert "[Regex]::Escape($marker)" not in script
    assert "$cmdLower.Contains($marker)" not in script


def test_launcher_profile_pattern_rejects_adjacent_profile_names(tmp_path):
    profile_dir = tmp_path / "APS" / "Chrome109Profile"
    marker = str(profile_dir).lower()

    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}" --app=http://127.0.0.1:5000', marker
    )
    assert _command_line_matches_exact_profile(
        f'chrome.exe "--user-data-dir={marker}" --app=http://127.0.0.1:5000', marker
    )
    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker.replace("chrome109profile", "Chrome109Profile")}"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}2" --app=http://127.0.0.1:5000',
        marker,
    )
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}_bak"', marker)
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --disk-cache-dir="{marker}" --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --app="http://127.0.0.1:5000/?q= --user-data-dir={marker} " --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --note="before --user-data-dir=\\"{marker}\\" after" --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={marker} \\"" --user-data-dir="d:\\other"',
        marker,
    )


def test_installer_profile_patterns_reject_adjacent_profile_names():
    exact_marker = r"c:\users\alice\appdata\local\aps\chrome109profile"
    suffix_marker = r"\aps\chrome109profile"
    other_user_profile = r"d:\other-user\appdata\local\aps\chrome109profile"

    assert _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}2" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}_bak"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}2"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}_bak"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --disk-cache-dir="{other_user_profile}" --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --app="http://127.0.0.1:5000/?q= --user-data-dir={other_user_profile} " --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={other_user_profile} \\"" --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )


def test_wait_for_runtime_stop_rechecks_after_last_sleep(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    status_snapshots = iter(
        [
            {"state": "mixed"},
            {"state": "active"},
            {"state": "stale"},
        ]
    )
    clock = iter([0.0, 0.3])

    monkeypatch.setattr(launcher_stop, "_classify_runtime_state", lambda state_dir: next(status_snapshots))
    monkeypatch.setattr(launcher_stop, "_runtime_stop_is_complete", lambda status: status["state"] == "stale")
    monkeypatch.setattr(launcher_stop.time, "time", lambda: next(clock))
    monkeypatch.setattr(launcher_stop.time, "sleep", lambda seconds: None)

    assert launcher_stop._wait_for_runtime_stop(str(tmp_path), 0.25)["state"] == "stale"


def test_force_kill_runtime_requires_confirmed_pid_match(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    base_status = {
        "contract_status": "valid",
        "contract": {"pid": 43210, "exe_path": sys.executable},
        "state": "active",
        "endpoint_up": True,
        "pid": 43210,
        "pid_exists": True,
        "expected_exe_path": sys.executable,
    }

    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_match": True}) is True
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_match": None}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_match": False}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_exists": False, "pid_match": True}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_exists": None, "pid_match": True}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "contract_status": "invalid", "pid_match": True}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid": "bad", "pid_match": True}) is False
    assert launcher_stop._can_force_kill_runtime({**base_status, "state": "mixed", "endpoint_up": False, "pid_match": True}) is True

    calls: List[int] = []
    status = {**base_status, "pid_match": None}
    monkeypatch.setattr(launcher_stop, "_kill_runtime_pid", lambda pid: calls.append(int(pid)) or True)
    assert launcher_stop._try_force_kill_runtime(str(tmp_path), status) is status
    assert calls == []

    stopped_status = {"state": "stale", "endpoint_up": False}
    monkeypatch.setattr(launcher_stop, "_wait_for_runtime_stop", lambda state_dir, deadline: stopped_status)
    assert launcher_stop._try_force_kill_runtime(str(tmp_path), {**base_status, "pid_match": True}) == stopped_status
    assert calls == [43210]


def test_stop_runtime_force_kills_mixed_endpoint_down_confirmed_pid(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "runtime" / "logs"
    mixed_status = {
        "contract_status": "valid",
        "contract": {"pid": 43210, "exe_path": sys.executable, "shutdown_token": "token"},
        "state": "mixed",
        "endpoint_up": False,
        "pid": 43210,
        "pid_exists": True,
        "pid_match": True,
        "state_dir": str(state_dir),
    }
    stopped_status = {**mixed_status, "state": "stale"}
    wait_results = iter([mixed_status, stopped_status])
    killed: List[int] = []
    finalized: List[dict] = []

    monkeypatch.setattr(launcher_stop, "_classify_runtime_state", lambda _state_dir: mixed_status)
    monkeypatch.setattr(launcher_stop, "_runtime_stop_is_complete", lambda status: status.get("state") == "stale")
    monkeypatch.setattr(launcher_stop, "_request_runtime_shutdown", lambda _contract, timeout_s=3.0: False)
    monkeypatch.setattr(launcher_stop, "_wait_for_runtime_stop", lambda _state_dir, _deadline: next(wait_results))
    monkeypatch.setattr(launcher_stop, "_kill_runtime_pid", lambda pid: killed.append(int(pid)) or True)

    def _finalize(status, runtime_dir_abs, *, stop_aps_chrome, logger):
        finalized.append({"status": status, "runtime_dir": runtime_dir_abs, "stop_aps_chrome": stop_aps_chrome})
        return 0

    monkeypatch.setattr(launcher_stop, "_finalize_stopped_runtime", _finalize)

    assert launcher_stop.stop_runtime_from_dir(str(runtime_dir), timeout_s=0.1) == 0
    assert killed == [43210]
    assert finalized[0]["status"] is stopped_status
    assert finalized[0]["runtime_dir"] == os.path.abspath(str(runtime_dir))


def test_launcher_stop_safe_int_only_swallows_parse_errors(capsys):
    launcher_stop = _import_launcher_stop()

    assert launcher_stop._safe_int("123") == 123
    assert launcher_stop._safe_int("bad") == 0
    assert "解析运行时整数失败" in capsys.readouterr().err

    class ExplodingInt:
        def __int__(self):
            raise RuntimeError("unexpected int failure")

    with pytest.raises(RuntimeError, match="unexpected int failure"):
        launcher_stop._safe_int(ExplodingInt())
    with pytest.raises(OverflowError):
        launcher_stop._safe_int(float("inf"))


def test_legacy_cleanup_success_is_verified_by_result_cleanup(tmp_path):
    cleanup = _import_launcher_stop_cleanup()
    cleanup_result = _import_launcher_cleanup_result()
    state_dir = tmp_path / "logs"
    mirror_dir = tmp_path / "mirror-logs"
    state_dir.mkdir()
    mirror_dir.mkdir()
    runtime_contract = state_dir / "aps_runtime.json"
    mirror_host = mirror_dir / "aps_host.txt"
    mirror_host.write_text("127.0.0.1\n", encoding="utf-8")
    payload = {
        "contract_version": 1,
        "pid": 123,
        "host": "127.0.0.1",
        "port": 5728,
        "shutdown_token": "token",
        "exe_path": sys.executable,
        "runtime_dir": str(tmp_path),
        "chrome_profile_dir": str(tmp_path / "chrome109_profile"),
        "data_dirs": {"log_dir": str(mirror_dir)},
    }
    runtime_contract.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (mirror_dir / "aps_runtime.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    legacy_calls: List[str] = []

    def _legacy_cleanup(path: str) -> None:
        legacy_calls.append(path)
        runtime_contract.unlink(missing_ok=True)

    def _default_legacy_cleanup(_path: str) -> None:
        raise AssertionError("default legacy cleanup should not be called")

    result = cleanup.delete_runtime_contract_files_result_for_stop(
        str(state_dir),
        delete_runtime_contract_files=_legacy_cleanup,
        delete_runtime_contract_files_result=cleanup_result.delete_runtime_contract_files_result,
        default_delete_runtime_contract_files=_default_legacy_cleanup,
        default_delete_runtime_contract_files_result=cleanup_result.delete_runtime_contract_files_result,
    )

    assert legacy_calls == [str(state_dir)]
    assert result.ok is True
    assert result.attempted_paths
    assert str(runtime_contract) in result.removed_paths
    assert str(mirror_host) in result.removed_paths
    assert not runtime_contract.exists()
    assert not mirror_host.exists()


def test_legacy_cleanup_failure_returns_failure_result(tmp_path):
    cleanup = _import_launcher_stop_cleanup()
    cleanup_result = _import_launcher_cleanup_result()
    state_dir = tmp_path / "logs"
    state_dir.mkdir()

    def _legacy_cleanup(_path: str) -> None:
        raise RuntimeError("legacy failed")

    def _default_legacy_cleanup(_path: str) -> None:
        raise AssertionError("default legacy cleanup should not be called")

    result = cleanup.delete_runtime_contract_files_result_for_stop(
        str(state_dir),
        delete_runtime_contract_files=_legacy_cleanup,
        delete_runtime_contract_files_result=cleanup_result.delete_runtime_contract_files_result,
        default_delete_runtime_contract_files=_default_legacy_cleanup,
        default_delete_runtime_contract_files_result=cleanup_result.delete_runtime_contract_files_result,
    )

    assert result.ok is False
    assert result.failures[0].reason == "legacy_cleanup_failed"
    assert "legacy failed" in result.failures[0].error


def test_stop_runtime_from_dir_reports_chrome_stop_failure_reason_without_logger(monkeypatch, tmp_path, capsys):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: None)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert "chrome_stop" in capsys.readouterr().err


def test_runtime_stop_failure_reports_reason_without_logger(capsys):
    launcher_stop = _import_launcher_stop()
    status = {
        "state": "mixed",
        "pid": 43210,
        "pid_exists": None,
        "pid_match": None,
        "host": "127.0.0.1",
        "port": 5000,
        "endpoint_up": False,
        "lock_active": True,
    }

    launcher_stop._log_runtime_stop_failure(status, shutdown_requested=False, logger=None)

    stderr = capsys.readouterr().err
    assert "runtime_stop_failed" in stderr
    assert "mixed_state" in stderr
    assert "pid_exists=None" in stderr


def test_runtime_stop_cli_passes_stop_aps_chrome_flag():
    from web.bootstrap.entrypoint import EntryPointDeps, app_main

    calls = {}

    deps = EntryPointDeps(
        create_app=lambda: Flask("unused-runtime-stop-test"),
        clear_launch_error=lambda *args, **kwargs: None,
        write_launch_error=lambda *args, **kwargs: None,
        current_runtime_owner=lambda: "LOCALBOX\\alice",
        resolve_prelaunch_log_dir=lambda runtime_dir: os.path.join(runtime_dir, "logs"),
        acquire_runtime_lock=lambda *args, **kwargs: {},
        release_runtime_lock=lambda *args, **kwargs: None,
        delete_runtime_contract_files=lambda *args, **kwargs: None,
        write_runtime_host_port_files=lambda *args, **kwargs: None,
        write_runtime_contract_file=lambda *args, **kwargs: "",
        default_chrome_profile_dir=lambda runtime_dir: os.path.join(runtime_dir, "chrome109_profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred, logger=None: (host, int(preferred)),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: (
            calls.setdefault("stop", (runtime_dir, stop_aps_chrome)) and 0
        ),
        serve_runtime_app=lambda app, host, port: None,
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        should_register_runtime_lifecycle_handlers=lambda debug: True,
        atexit_register=lambda *args, **kwargs: None,
    )

    assert (
        app_main("default", anchor_file=__file__, argv=["--runtime-stop", "D:/runtime", "--stop-aps-chrome"], deps=deps)
        == 0
    )
    assert calls["stop"] == ("D:/runtime", True)
