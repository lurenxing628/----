from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional, Tuple

from .launcher_observability import launcher_log_warning

_PROCESS_LOG_STATE_DIR = ""
_PROCESS_LOG_RUNTIME_DIR = ""


def set_process_log_context(*, state_dir: str = "", runtime_dir: str = "") -> None:
    global _PROCESS_LOG_STATE_DIR, _PROCESS_LOG_RUNTIME_DIR
    _PROCESS_LOG_STATE_DIR = str(state_dir or "").strip()
    _PROCESS_LOG_RUNTIME_DIR = str(runtime_dir or "").strip()


def _process_log_warning(logger: Optional[logging.Logger], message: str, *args) -> None:
    launcher_log_warning(
        logger,
        message,
        *args,
        state_dir=_PROCESS_LOG_STATE_DIR or None,
        runtime_dir=_PROCESS_LOG_RUNTIME_DIR or None,
    )


def _parse_pid(pid: int) -> int:
    try:
        return int(pid)
    except Exception as exc:
        _process_log_warning(None, "解析运行时 pid 失败，已按不存在处理：pid=%r error=%s", pid, exc)
        return 0


def _windows_pid_state(pid_i: int) -> Optional[bool]:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid_i}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception as exc:
        _process_log_warning(None, "枚举 Windows pid 失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None
    if int(result.returncode or 0) != 0:
        _process_log_warning(
            None,
            "枚举 Windows pid 返回失败，运行时身份状态未知：pid=%s rc=%s stderr=%s",
            pid_i,
            result.returncode,
            (result.stderr or "").strip(),
        )
        return None
    for line in (result.stdout or "").splitlines():
        line_s = str(line or "").strip()
        if line_s.startswith('"') and f',"{pid_i}",' in line_s:
            return True
    return False


def _posix_pid_state(pid_i: int) -> Optional[bool]:
    try:
        os.kill(pid_i, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        _process_log_warning(None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None
    except Exception as exc:
        _process_log_warning(None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None


def _pid_state(pid: int) -> Optional[bool]:
    pid_i = _parse_pid(pid)
    if pid_i <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_state(pid_i)
    return _posix_pid_state(pid_i)


def _pid_exists(pid: int) -> bool:
    state = _pid_state(pid)
    if state is None:
        return False
    return bool(state)


def runtime_pid_state(pid: int) -> Optional[bool]:
    """公开三态探针：True=存在，False=不存在，None=无法确认。"""

    return _pid_state(pid)


def runtime_pid_exists(pid: int) -> bool:
    """公开兼容探针：仅用于展示；安全关键链路应使用 runtime_pid_state。"""

    return runtime_pid_state(pid) is True


def _run_powershell_text(script: str, timeout_s: float = 8.0) -> Tuple[Optional[int], str]:
    if os.name != "nt":
        return None, ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=max(float(timeout_s), 0.5),
            check=False,
    )
    except Exception as exc:
        _process_log_warning(None, "PowerShell 运行失败，相关运行时能力不可确认：%s", exc)
        return None, ""
    output = (result.stdout or "").strip()
    stderr_text = (result.stderr or "").strip()
    if stderr_text:
        output = output + ("\n" if output else "") + stderr_text
    return int(result.returncode or 0), output


def _query_process_executable_path(pid: int) -> Optional[str]:
    try:
        pid_i = int(pid)
    except Exception as exc:
        _process_log_warning(None, "解析进程路径 pid 失败，无法确认运行时身份：pid=%r error=%s", pid, exc)
        return None
    if pid_i <= 0:
        return None
    if os.name != "nt":
        return None
    script = (
        "$ErrorActionPreference='Stop';"
        f"$pid0={pid_i};"
        "$proc = $null;"
        "if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {"
        "try { $proc = Get-CimInstance Win32_Process -Filter \"ProcessId=$pid0\" -ErrorAction Stop | Select-Object -First 1 }"
        "catch { $proc = $null }"
        "}"
        "if ($null -eq $proc) {"
        "if (-not (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) { exit 1 };"
        "try { $proc = Get-WmiObject Win32_Process -Filter \"ProcessId=$pid0\" -ErrorAction Stop | Select-Object -First 1 }"
        "catch { exit 1 }"
        "}"
        "$path = [string]$proc.ExecutablePath;"
        "if ($null -eq $path -or $path.Trim().Length -eq 0) { exit 2 };"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "Write-Output $path;"
        "exit 0"
    )
    rc, output = _run_powershell_text(script, timeout_s=8.0)
    if rc == 2:
        _process_log_warning(None, "进程路径为空，无法确认运行时身份：pid=%s", pid_i)
        return ""
    if rc is None or rc != 0:
        _process_log_warning(None, "查询进程路径失败，无法确认运行时身份：pid=%s rc=%s", pid_i, rc)
        return None
    for line in str(output or "").splitlines():
        value_s = str(line or "").strip()
        if value_s:
            return os.path.normcase(os.path.abspath(value_s))
    return ""


def _pid_matches_contract(pid: int, expected_exe_path: str) -> Optional[bool]:
    actual = _query_process_executable_path(pid)
    if actual is None:
        return None
    if actual == "":
        return False
    expected = os.path.normcase(os.path.abspath(str(expected_exe_path or "").strip()))
    if not expected:
        return None
    return actual == expected


def runtime_pid_matches_executable(pid: int, expected_exe_path: str) -> Optional[bool]:
    """公开只读探针：判断 pid 是否匹配期望可执行文件路径。"""

    return _pid_matches_contract(pid, expected_exe_path)


def _kill_runtime_pid(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except Exception as exc:
        _process_log_warning(None, "解析待强制停止 pid 失败，已拒绝强杀：pid=%r error=%s", pid, exc)
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid_i), "/F", "/T"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
        )
        except Exception as exc:
            _process_log_warning(None, "强制停止运行时 pid 失败：pid=%s error=%s", pid_i, exc)
            return False
        ok = int(result.returncode or 0) == 0
        if not ok:
            _process_log_warning(
                None,
                "强制停止运行时 pid 返回失败：pid=%s rc=%s stderr=%s",
                pid_i,
                result.returncode,
                (result.stderr or "").strip(),
            )
        return ok
    return False
