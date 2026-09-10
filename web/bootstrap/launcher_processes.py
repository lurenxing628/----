from __future__ import annotations

import base64
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


def _log_warning(logger: Optional[logging.Logger], message: str, *args) -> None:
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
    except (TypeError, ValueError, OverflowError) as exc:
        _log_warning(None, "解析运行时 pid 失败，已按不存在处理：pid=%r error=%s", pid, exc)
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
        _log_warning(None, "枚举 Windows pid 失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None
    if int(result.returncode or 0) != 0:
        _log_warning(
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
        _log_warning(None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
        return None
    except Exception as exc:
        _log_warning(None, "探测 pid 存活状态失败，运行时身份状态未知：pid=%s error=%s", pid_i, exc)
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
        _log_warning(None, "PowerShell 运行失败，相关运行时能力不可确认：%s", exc)
        return None, ""
    output = (result.stdout or "").strip()
    stderr_text = (result.stderr or "").strip()
    if stderr_text:
        output = output + ("\n" if output else "") + stderr_text
    return int(result.returncode or 0), output


def _run_powershell_bytes(script: str, timeout_s: float = 8.0) -> Tuple[Optional[int], bytes, bytes]:
    """运行 PowerShell 并返回 (rc, stdout 字节, stderr 字节)，不做任何文本解码。

    可能含非 ASCII（如中文安装路径）的输出必须走本通道：Win7 PowerShell 2.0
    的控制台输出编码不可控（OEM/cp936），文本通道按 UTF-8 + errors=ignore 解码
    会把中文字节静默吞掉，导致运行时身份误判（audit 2026-07-19 D02）。
    只捕获子进程可预期的失败（缺 PowerShell、超时等），留痕后返回 None 三元组；
    其余异常照常抛出，不做宽兜底。
    """
    if os.name != "nt":
        return None, b"", b""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            timeout=max(float(timeout_s), 0.5),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log_warning(None, "PowerShell 运行失败，相关运行时能力不可确认：%s", exc)
        return None, b"", b""
    return int(result.returncode or 0), bytes(result.stdout or b""), bytes(result.stderr or b"")


def _decode_base64_path_output(output: bytes, pid_i: int) -> Optional[str]:
    """解码 base64 通道输出的进程路径；任何失败都留痕并返回 None（身份未知）。

    不做 errors=ignore/replace 兜底：解不出来就是无法确认运行时身份，
    让 _pid_matches_contract 的三态判定走安全侧（None）。
    """
    try:
        text = output.decode("ascii")
    except UnicodeDecodeError as exc:
        _log_warning(
            None,
            "进程路径输出应为 base64（纯 ASCII）但含其他字节，无法确认运行时身份：pid=%s error=%s raw=%r",
            pid_i,
            exc,
            output[:200],
        )
        return None
    token = ""
    for line in text.splitlines():
        line_s = line.strip()
        if line_s:
            token = line_s
            break
    if not token:
        _log_warning(None, "进程路径查询返回成功但无输出，无法确认运行时身份：pid=%s", pid_i)
        return None
    try:
        raw = base64.b64decode(token, validate=True)
    except ValueError as exc:
        # binascii.Error 是 ValueError 子类
        _log_warning(
            None,
            "进程路径 base64 解码失败，无法确认运行时身份：pid=%s error=%s token=%r",
            pid_i,
            exc,
            token[:200],
        )
        return None
    try:
        value_s = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _log_warning(
            None,
            "进程路径 UTF-8 解码失败，无法确认运行时身份：pid=%s error=%s raw=%r",
            pid_i,
            exc,
            raw[:200],
        )
        return None
    value_s = value_s.strip()
    if not value_s:
        _log_warning(None, "进程路径解码结果为空，无法确认运行时身份：pid=%s", pid_i)
        return None
    return value_s


def _query_process_executable_path(pid: int) -> Optional[str]:
    try:
        pid_i = int(pid)
    except (TypeError, ValueError, OverflowError) as exc:
        _log_warning(None, "解析进程路径 pid 失败，无法确认运行时身份：pid=%r error=%s", pid, exc)
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
        # 路径可能含中文：Win7 PS2.0 上 [Console]::OutputEncoding=UTF8 技巧不可靠，
        # 改输出路径 UTF-8 字节的 base64（PS2.0/.NET2.0 即支持 ToBase64String），
        # base64 是纯 ASCII，任何控制台代码页都不会损坏它。
        "Write-Output ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($path)));"
        "exit 0"
    )
    rc, stdout_bytes, stderr_bytes = _run_powershell_bytes(script, timeout_s=8.0)
    if rc == 2:
        _log_warning(None, "进程路径为空，无法确认运行时身份：pid=%s", pid_i)
        return ""
    if rc is None or rc != 0:
        _log_warning(
            None,
            "查询进程路径失败，无法确认运行时身份：pid=%s rc=%s stderr=%r",
            pid_i,
            rc,
            stderr_bytes[:200],
        )
        return None
    value_s = _decode_base64_path_output(stdout_bytes, pid_i)
    if value_s is None:
        return None
    return os.path.normcase(os.path.abspath(value_s))


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
    except (TypeError, ValueError, OverflowError) as exc:
        _log_warning(None, "解析待强制停止 pid 失败，已拒绝强杀：pid=%r error=%s", pid, exc)
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
            _log_warning(None, "强制停止运行时 pid 失败：pid=%s error=%s", pid_i, exc)
            return False
        ok = int(result.returncode or 0) == 0
        if not ok:
            _log_warning(
                None,
                "强制停止运行时 pid 返回失败：pid=%s rc=%s stderr=%s",
                pid_i,
                result.returncode,
                (result.stderr or "").strip(),
            )
        return ok
    return False
