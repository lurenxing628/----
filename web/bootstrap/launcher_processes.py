from __future__ import annotations

import os
import subprocess
from typing import Optional


def _pid_exists(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_i}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return False
        for line in (result.stdout or "").splitlines():
            line_s = str(line or "").strip()
            if line_s.startswith('"') and f',"{pid_i}",' in line_s:
                return True
        return False
    try:
        os.kill(pid_i, 0)
        return True
    except Exception:
        return False


def runtime_pid_exists(pid: int) -> bool:
    """公开只读探针：判断给定 pid 当前是否存在。"""

    return _pid_exists(pid)


def _run_powershell_text(script: str, timeout_s: float = 8.0) -> tuple[Optional[int], str]:
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
    except Exception:
        return None, ""
    output = (result.stdout or "").strip()
    stderr_text = (result.stderr or "").strip()
    if stderr_text:
        output = output + ("\n" if output else "") + stderr_text
    return int(result.returncode or 0), output


def _query_process_executable_path(pid: int) -> Optional[str]:
    try:
        pid_i = int(pid)
    except Exception:
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
        return ""
    if rc is None or rc != 0:
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
    except Exception:
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
        except Exception:
            return False
        return int(result.returncode or 0) == 0
    return False
