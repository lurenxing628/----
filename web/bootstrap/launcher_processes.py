from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional, Tuple

from . import launcher_win32
from .launcher_observability import launcher_log_warning

_PROCESS_LOG_STATE_DIR = ""
_PROCESS_LOG_RUNTIME_DIR = ""
_POWERSHELL_TIMEOUT_S = 8.0


def set_process_log_context(*, state_dir: str = "", runtime_dir: str = "") -> None:
    global _PROCESS_LOG_STATE_DIR, _PROCESS_LOG_RUNTIME_DIR
    _PROCESS_LOG_STATE_DIR = state_dir
    _PROCESS_LOG_RUNTIME_DIR = runtime_dir


def _log_warning(logger: Optional[logging.Logger], message: str, *args) -> None:
    launcher_log_warning(
        logger,
        message,
        *args,
        state_dir=_PROCESS_LOG_STATE_DIR or None,
        runtime_dir=_PROCESS_LOG_RUNTIME_DIR or None,
    )


def _windows_pid_state(pid_i: int) -> Optional[bool]:
    try:
        return launcher_win32.pid_exists(pid_i)
    except OSError as exc:
        _log_warning(None, "Windows pid 探测失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None


def _posix_pid_state(pid_i: int) -> Optional[bool]:
    try:
        os.kill(pid_i, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception as exc:
        _log_warning(None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None


def _pid_state(pid: int) -> Optional[bool]:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_state(pid)
    return _posix_pid_state(pid)


def run_powershell_text(script: str) -> Tuple[Optional[int], str]:
    if os.name != "nt":
        return None, ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=_POWERSHELL_TIMEOUT_S,
            check=False,
        )
    except Exception as exc:
        _log_warning(None, "PowerShell 运行失败，相关运行时能力不可确认：%s", exc)
        return None, ""
    output = result.stdout.strip()
    stderr_text = result.stderr.strip()
    if stderr_text:
        output = output + ("\n" if output else "") + stderr_text
    return result.returncode, output


def _query_process_executable_path(pid: int) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        path = launcher_win32.executable_path(pid)
        return os.path.normcase(os.path.abspath(path)) if path else ""
    except OSError as exc:
        _log_warning(None, "查询进程路径失败，无法确认运行时身份：pid=%s error=%s", pid, exc)
        return None


def _pid_matches_contract(pid: int, expected_exe_path: str) -> Optional[bool]:
    actual = _query_process_executable_path(pid)
    if actual is None:
        return None
    if actual == "":
        return False
    return actual == os.path.normcase(os.path.abspath(expected_exe_path))


def kill_runtime_pid(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
        )
        except Exception as exc:
            _log_warning(None, "强制停止运行时 pid 失败：pid=%s error=%s", pid, exc)
            return False
        ok = result.returncode == 0
        if not ok:
            _log_warning(
                None,
                "强制停止运行时 pid 返回失败：pid=%s rc=%s stderr=%s",
                pid,
                result.returncode,
                result.stderr.strip(),
            )
        return ok
    return False
