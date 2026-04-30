from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from web.bootstrap.entrypoint import _write_launch_error_with_observability
from web.bootstrap.launcher_contracts import release_runtime_lock
from web.bootstrap.launcher_network import pick_port
from web.bootstrap.launcher_observability import launcher_log_warning
from web.bootstrap.launcher_processes import _run_powershell_text, set_process_log_context


def test_launcher_log_warning_writes_state_dir_launcher_log(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"

    result = launcher_log_warning(None, "hello %s", "state", state_dir=str(state_dir))

    assert result.file_ok
    assert (state_dir / "launcher.log").read_text(encoding="utf-8").endswith("hello state\n")


def test_launcher_log_warning_writes_cfg_log_dir_launcher_log(tmp_path: Path) -> None:
    cfg_log_dir = tmp_path / "configured-logs"

    result = launcher_log_warning(None, "hello cfg", cfg_log_dir=str(cfg_log_dir))

    assert result.file_ok
    assert (cfg_log_dir / "launcher.log").read_text(encoding="utf-8").endswith("hello cfg\n")


def test_launcher_log_warning_writes_runtime_logs_launcher_log(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    result = launcher_log_warning(None, "hello runtime", runtime_dir=str(runtime_dir))

    assert result.file_ok
    assert (runtime_dir / "logs" / "launcher.log").read_text(encoding="utf-8").endswith("hello runtime\n")


def test_launcher_log_warning_treats_logs_runtime_dir_as_state_dir(tmp_path: Path) -> None:
    state_dir = tmp_path / "runtime" / "logs"

    result = launcher_log_warning(None, "hello logs", runtime_dir=str(state_dir))

    assert result.file_ok
    assert (state_dir / "launcher.log").read_text(encoding="utf-8").endswith("hello logs\n")
    assert not (state_dir / "logs").exists()


def test_launcher_log_warning_writes_launch_error_file(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"

    result = launcher_log_warning(None, "visible failure", state_dir=str(state_dir), write_launch_error=True)

    assert result.file_ok
    assert result.error_file_ok
    assert "visible failure" in (state_dir / "aps_launch_error.txt").read_text(encoding="utf-8")


def test_launcher_log_warning_reports_file_write_failure(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"

    def _boom_makedirs(*_args, **_kwargs) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr("web.bootstrap.launcher_observability.os.makedirs", _boom_makedirs)

    result = launcher_log_warning(None, "cannot write file", state_dir=str(state_dir))

    assert not result.file_ok
    assert result.stderr_ok
    assert result.errors


def test_launcher_log_warning_does_not_recurse_when_stderr_fails(monkeypatch, tmp_path: Path) -> None:
    class _BrokenStderr:
        def write(self, _text: str) -> int:
            raise RuntimeError("stderr broken")

        def flush(self) -> None:
            raise RuntimeError("stderr broken")

    def _boom_makedirs(*_args, **_kwargs) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr("web.bootstrap.launcher_observability.os.makedirs", _boom_makedirs)
    monkeypatch.setattr(sys, "stderr", _BrokenStderr())

    result = launcher_log_warning(None, "cannot write anywhere", state_dir=str(tmp_path / "logs"))

    assert not result.file_ok
    assert not result.stderr_ok
    assert any("stderr" in error for error in result.errors)


def test_process_probe_failure_uses_configured_state_dir(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    set_process_log_context(state_dir=str(state_dir))
    monkeypatch.setattr("web.bootstrap.launcher_processes.os.name", "nt")

    def _boom_run(*_args, **_kwargs):
        raise OSError("powershell missing")

    monkeypatch.setattr("web.bootstrap.launcher_processes.subprocess.run", _boom_run)

    rc, output = _run_powershell_text("Write-Output 1")

    assert rc is None
    assert output == ""
    assert "PowerShell 运行失败" in (state_dir / "launcher.log").read_text(encoding="utf-8")
    set_process_log_context()


def test_pick_port_fallback_writes_state_dir_launcher_log(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    monkeypatch.setattr("web.bootstrap.launcher_network._can_bind", lambda _host, _port: False)

    host, port = pick_port("127.0.0.1", 6123, state_dir=str(state_dir))

    assert host == "127.0.0.1"
    assert int(port) > 0
    assert "固定候选端口均不可用" in (state_dir / "launcher.log").read_text(encoding="utf-8")


def test_entrypoint_launch_error_write_failure_uses_launcher_log(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"

    def _boom_write_launch_error(*_args, **_kwargs) -> None:
        raise OSError("disk locked")

    deps = SimpleNamespace(write_launch_error=_boom_write_launch_error)

    _write_launch_error_with_observability(
        deps,
        str(runtime_dir),
        "启动失败",
        str(state_dir),
        logger=None,
        context="启动失败",
    )

    assert "写入启动错误文件失败" in (state_dir / "launcher.log").read_text(encoding="utf-8")


def test_release_runtime_lock_remove_failure_uses_launcher_log(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = state_dir / "aps_runtime.lock"
    lock_path.write_text(
        "pid=12345\nowner=tester\nexe_path=/tmp/aps.exe\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("web.bootstrap.launcher_contracts.os.getpid", lambda: 12345)

    def _boom_remove(path: str) -> None:
        if str(path) == str(lock_path):
            raise PermissionError("locked")

    monkeypatch.setattr("web.bootstrap.launcher_contracts.os.remove", _boom_remove)

    release_runtime_lock(str(state_dir))

    assert lock_path.exists()
    assert "释放运行时锁失败" in (state_dir / "launcher.log").read_text(encoding="utf-8")
