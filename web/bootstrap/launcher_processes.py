from __future__ import annotations

import os
import subprocess
from typing import Optional, Tuple

from . import launcher_win32
from .launcher_observability import launcher_log_warning

_POWERSHELL_TIMEOUT_S = 8.0


def _windows_pid_state(pid_i: int, *, state_dir: Optional[str]) -> Optional[bool]:
    try:
        return launcher_win32.pid_exists(pid_i)
    except OSError as exc:
        launcher_log_warning(
            None, "Windows pid 探测失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc, state_dir=state_dir
        )
        return None


def _posix_pid_state(pid_i: int, *, state_dir: Optional[str]) -> Optional[bool]:
    try:
        os.kill(pid_i, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError) as exc:
        launcher_log_warning(
            None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc, state_dir=state_dir
        )
        return None


def query_pid_state(pid: int, *, state_dir: Optional[str]) -> Optional[bool]:
    """pid 是否存活：True 存活，False 已退出，None 无法确认。state_dir 为 None 时探测失败只写 stderr。"""
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_state(pid, state_dir=state_dir)
    return _posix_pid_state(pid, state_dir=state_dir)


def run_powershell_text(script: str, *, state_dir: Optional[str]) -> Tuple[Optional[int], str]:
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
    except (OSError, subprocess.SubprocessError) as exc:
        launcher_log_warning(None, "PowerShell 运行失败，相关运行时能力不可确认：%s", exc, state_dir=state_dir)
        return None, ""
    output = result.stdout.strip()
    stderr_text = result.stderr.strip()
    if stderr_text:
        output = output + ("\n" if output else "") + stderr_text
    return result.returncode, output


def _query_process_executable_path(pid: int, *, state_dir: Optional[str]) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        path = launcher_win32.executable_path(pid)
        return os.path.normcase(os.path.abspath(path)) if path else ""
    except OSError as exc:
        launcher_log_warning(
            None, "查询进程路径失败，无法确认运行时身份：pid=%s error=%s", pid, exc, state_dir=state_dir
        )
        return None


def pid_matches_contract(pid: int, expected_exe_path: str, *, state_dir: Optional[str]) -> Optional[bool]:
    """pid 对应的可执行文件是否就是契约记录的那个：None 表示无法确认。"""
    actual = _query_process_executable_path(pid, state_dir=state_dir)
    if actual is None:
        return None
    if actual == "":
        return False
    return actual == os.path.normcase(os.path.abspath(expected_exe_path))


def kill_runtime_pid(pid: int, *, state_dir: Optional[str]) -> bool:
    if os.name == "nt":
        try:
            # taskkill 按系统代码页输出，只进日志；解码不了的字节替换掉，不让它变成异常。
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            launcher_log_warning(None, "强制停止运行时 pid 失败：pid=%s error=%s", pid, exc, state_dir=state_dir)
            return False
        ok = result.returncode == 0
        if not ok:
            launcher_log_warning(
                None,
                "强制停止运行时 pid 返回失败：pid=%s rc=%s stderr=%s",
                pid,
                result.returncode,
                result.stderr.strip(),
                state_dir=state_dir,
            )
        return ok
    return False
