"""回归测试：启动器可观测性——launcher_log_warning 把原始诊断写入 launcher.log（含路径/密钥），但 aps_launch_error.txt 只给脱敏公开文案；正确选择 state_dir/cfg_log_dir/runtime/logs 落点、支持 error 级别、文件或 stderr 写失败时不递归并报告；entrypoint 启动错误不重复写、不向 stderr 泄原文、写失败仍守住返回码契约；app.py 导入失败抛公开 RuntimeError 同时把原文写进 launcher.log；释放运行时锁失败也落 launcher.log。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._support.paths import REPO_ROOT
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

    result = launcher_log_warning(
        None,
        "path=/Users/me/private.db error=SECRET_TOKEN",
        state_dir=str(state_dir),
        write_launch_error=True,
        public_launch_error_message="应用启动失败，请联系维护人员。",
    )

    assert result.file_ok
    assert result.error_file_ok
    launch_error = (state_dir / "aps_launch_error.txt").read_text(encoding="utf-8")
    launcher_log = (state_dir / "launcher.log").read_text(encoding="utf-8")
    assert "应用启动失败，请联系维护人员。" in launch_error
    assert "/Users/me" not in launch_error
    assert "private.db" not in launch_error
    assert "SECRET_TOKEN" not in launch_error
    assert "SECRET_TOKEN" in launcher_log


def test_launcher_log_warning_default_launch_error_is_public(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"

    result = launcher_log_warning(
        None,
        "SECRET_TOKEN /tmp/private.db",
        state_dir=str(state_dir),
        write_launch_error=True,
    )

    assert result.file_ok
    launch_error = (state_dir / "aps_launch_error.txt").read_text(encoding="utf-8")
    launcher_log = (state_dir / "launcher.log").read_text(encoding="utf-8")
    assert "应用启动时遇到问题" in launch_error
    assert "SECRET_TOKEN" not in launch_error
    assert "/tmp/private.db" not in launch_error
    assert "SECRET_TOKEN" in launcher_log
    assert "/tmp/private.db" in launcher_log


def test_launcher_log_warning_uses_error_level_in_launcher_log(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"

    result = launcher_log_warning(None, "serious failure", state_dir=str(state_dir), logger_level="error")

    assert result.file_ok
    assert "[ERROR] serious failure" in (state_dir / "launcher.log").read_text(encoding="utf-8")


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


def test_entrypoint_launch_error_is_not_written_twice(tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"
    write_launch_error_calls = []

    def _unexpected_write_launch_error(*_args, **_kwargs) -> None:
        write_launch_error_calls.append(_args)

    deps = SimpleNamespace(write_launch_error=_unexpected_write_launch_error)

    _write_launch_error_with_observability(
        deps,
        str(runtime_dir),
        "启动失败 SECRET_TOKEN",
        str(state_dir),
        logger=None,
        context="启动失败",
    )

    launcher_log = (state_dir / "launcher.log").read_text(encoding="utf-8")
    launch_error = (state_dir / "aps_launch_error.txt").read_text(encoding="utf-8")
    assert write_launch_error_calls == []
    assert "SECRET_TOKEN" in launcher_log
    assert "SECRET_TOKEN" not in launch_error


def test_entrypoint_launch_error_does_not_send_raw_message_to_stderr(tmp_path: Path, capsys) -> None:
    state_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"
    deps = SimpleNamespace(write_launch_error=lambda *_args, **_kwargs: None)

    _write_launch_error_with_observability(
        deps,
        str(runtime_dir),
        "启动失败 SECRET_TOKEN /tmp/private.db",
        str(state_dir),
        logger=None,
        context="启动失败 SECRET_TOKEN /tmp/private.db",
    )

    stderr_text = capsys.readouterr().err
    launch_error = (state_dir / "aps_launch_error.txt").read_text(encoding="utf-8")
    launcher_log = (state_dir / "launcher.log").read_text(encoding="utf-8")
    assert "SECRET_TOKEN" not in stderr_text
    assert "/tmp/private.db" not in stderr_text
    assert "SECRET_TOKEN" not in launch_error
    assert "/tmp/private.db" not in launch_error
    assert "SECRET_TOKEN" in launcher_log
    assert "/tmp/private.db" in launcher_log


def test_entrypoint_launch_error_file_write_failure_keeps_return_code_contract(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    state_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"
    write_launch_error_calls = []

    def _fail_error_file(path, text, attempted_paths, errors) -> bool:
        attempted_paths.append(str(path))
        errors.append("error-file:locked")
        return False

    deps = SimpleNamespace(write_launch_error=lambda *_args, **_kwargs: write_launch_error_calls.append(_args))
    monkeypatch.setattr("web.bootstrap.launcher_observability._write_text_file", _fail_error_file)

    ok = _write_launch_error_with_observability(
        deps,
        str(runtime_dir),
        "启动失败 SECRET_TOKEN",
        str(state_dir),
        logger=None,
        context="启动失败",
    )

    stderr_text = capsys.readouterr().err
    launcher_log = (state_dir / "launcher.log").read_text(encoding="utf-8")
    assert ok is False
    assert "应用启动失败：程序没有正常启动" in stderr_text
    assert "SECRET_TOKEN" not in stderr_text
    assert str(state_dir / "aps_launch_error.txt") not in stderr_text
    assert "SECRET_TOKEN" in launcher_log
    assert "写入启动错误提示文件失败" in launcher_log
    assert "error-file:locked" not in launcher_log
    assert not write_launch_error_calls
    assert not (state_dir / "aps_launch_error.txt").exists()


def test_entrypoint_launch_error_log_write_failure_keeps_return_code_contract(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    state_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"

    def _boom_makedirs(*_args, **_kwargs) -> None:
        raise PermissionError("locked")

    deps = SimpleNamespace(write_launch_error=lambda *_args, **_kwargs: None)
    monkeypatch.setattr("web.bootstrap.launcher_observability.os.makedirs", _boom_makedirs)

    ok = _write_launch_error_with_observability(
        deps,
        str(runtime_dir),
        "启动失败 SECRET_TOKEN",
        str(state_dir),
        logger=None,
        context="启动失败 SECRET_TOKEN",
    )

    stderr_text = capsys.readouterr().err
    assert ok is False
    assert "应用启动失败：程序没有正常启动" in stderr_text
    assert "SECRET_TOKEN" not in stderr_text
    assert not (state_dir / "launcher.log").exists()


def test_app_import_failure_raises_public_error_and_writes_raw_launcher_log(monkeypatch, tmp_path: Path) -> None:
    from web.bootstrap import entrypoint as entrypoint_module

    public_message = "应用启动失败：程序文件加载失败，请把 launcher.log 发给维护人员排查。"
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))

    def _boom_create_app(_ui_mode: str):
        raise RuntimeError("SECRET_TOKEN /tmp/private.db")

    monkeypatch.setattr(entrypoint_module, "create_app_with_mode", _boom_create_app)
    module_name = "_aps_app_import_failure_probe"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "app.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(RuntimeError) as exc_info:
        spec.loader.exec_module(module)

    assert str(exc_info.value) == public_message
    launch_error = (log_dir / "aps_launch_error.txt").read_text(encoding="utf-8")
    launcher_log = (log_dir / "launcher.log").read_text(encoding="utf-8")
    assert "程序文件加载失败" in launch_error
    assert "SECRET_TOKEN" not in launch_error
    assert "/tmp/private.db" not in launch_error
    assert "SECRET_TOKEN" in launcher_log
    assert "/tmp/private.db" in launcher_log


def test_app_import_failure_keeps_public_error_when_launcher_log_cannot_be_written(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from web.bootstrap import entrypoint as entrypoint_module

    log_dir = tmp_path / "logs"
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))

    def _boom_create_app(_ui_mode: str):
        raise RuntimeError("SECRET_TOKEN /tmp/private.db")

    def _boom_makedirs(*_args, **_kwargs) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr(entrypoint_module, "create_app_with_mode", _boom_create_app)
    monkeypatch.setattr("web.bootstrap.launcher_observability.os.makedirs", _boom_makedirs)
    module_name = "_aps_app_import_failure_no_log_probe"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "app.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(RuntimeError) as exc_info:
        spec.loader.exec_module(module)

    stderr_text = capsys.readouterr().err
    assert "应用启动失败：程序文件加载失败" in stderr_text
    assert "SECRET_TOKEN" not in stderr_text
    assert "应用启动失败：程序文件加载失败" in str(exc_info.value)
    assert "SECRET_TOKEN" not in str(exc_info.value)
    assert not (log_dir / "launcher.log").exists()
    assert not (log_dir / "aps_launch_error.txt").exists()


def test_release_runtime_lock_remove_failure_uses_launcher_log(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    lock_path = state_dir / "aps_runtime.lock"
    lock_path.write_text(
        "pid=12345\nowner=tester\nexe_path=/tmp/aps.exe\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("web.bootstrap.launcher_contracts.os.getpid", lambda: 12345)

    def _boom_remove(path: str, **_kwargs) -> bool:
        if str(path) == str(lock_path):
            raise PermissionError("locked")
        return True

    monkeypatch.setattr("web.bootstrap.launcher_contracts.remove_fixed_file", _boom_remove)

    release_runtime_lock(str(state_dir))

    assert lock_path.exists()
    assert "释放运行时锁失败" in (state_dir / "launcher.log").read_text(encoding="utf-8")
