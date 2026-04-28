from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .launcher_contracts import (
    _is_runtime_lock_active,
    delete_runtime_contract_files,
    read_runtime_contract,
    read_runtime_lock,
)
from .launcher_paths import (
    RUNTIME_SHUTDOWN_PATH,
    default_chrome_profile_dir,
    resolve_runtime_state_paths,
    resolve_runtime_stop_context,
    state_contract_paths,
)
from .launcher_processes import _kill_runtime_pid, _pid_exists, _pid_matches_contract, _run_powershell_text


@dataclass(frozen=True)
class _StopChromeResult:
    ok: bool
    status: str
    profile_dir: str
    pids: list[int]
    remaining_pids: list[int]
    failed_pids: list[int]
    reason: str = ""


def _build_shutdown_url(contract: Dict[str, Any]) -> Optional[str]:
    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = int(contract.get("port") or 0)
    except Exception:
        port = 0
    if port <= 0:
        return None
    shutdown_path = str(contract.get("shutdown_path") or RUNTIME_SHUTDOWN_PATH).strip() or RUNTIME_SHUTDOWN_PATH
    if not shutdown_path.startswith("/"):
        shutdown_path = "/" + shutdown_path
    return f"http://{host}:{port}{shutdown_path}"


def _request_runtime_shutdown(contract: Dict[str, Any], timeout_s: float = 3.0) -> bool:
    url = _build_shutdown_url(contract)
    token = str(contract.get("shutdown_token") or "").strip()
    if not url or not token:
        return False
    req = urllib.request.Request(url, method="POST", data=b"")
    req.add_header("X-APS-Shutdown-Token", token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.5)) as resp:
            return int(getattr(resp, "status", 200)) < 400
    except urllib.error.HTTPError as e:
        return int(getattr(e, "code", 500)) < 400
    except Exception:
        return False


def _probe_runtime_health(host: str, port: int, timeout_s: float = 1.5) -> bool:
    url = f"http://{str(host or '').strip() or '127.0.0.1'}:{int(port)}/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.2)) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return False
    return (
        payload.get("app") == "aps"
        and payload.get("status") == "ok"
        and int(payload.get("contract_version") or 0) == 1
    )


def probe_runtime_health(host: str, port: int, timeout_s: float = 1.5) -> bool:
    """公开只读探针：按运行时健康接口口径探测目标实例是否健康。"""

    return _probe_runtime_health(host, port, timeout_s=timeout_s)


def _chrome_pid_query_script(profile_dir: str) -> str:
    marker = os.path.abspath(str(profile_dir or "").strip()).replace("'", "''").lower()
    return (
        "$ErrorActionPreference='Stop';"
        f"$marker='{marker}';"
        "$items = $null;"
        "if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {"
        "  try { $items = @(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) }"
        "  catch { $items = $null }"
        "}"
        "if ($null -eq $items -and (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) {"
        "  try { $items = @(Get-WmiObject Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) }"
        "  catch { exit 1 }"
        "}"
        "if ($null -eq $items) { exit 1 }"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "foreach ($item in $items) {"
        "  $cmd = [string]$item.CommandLine;"
        "  if (-not [string]::IsNullOrWhiteSpace($cmd)) {"
        "  $cmdLower = $cmd.ToLowerInvariant(); if ($cmdLower.Contains('--user-data-dir') -and $cmdLower.Contains($marker)) {"
        "    Write-Output ([string][int]$item.ProcessId)"
        "  } }"
        "}"
        "exit 0"
    )


def _parse_chrome_pid_output(output: str) -> list[int]:
    pids: list[int] = []
    for line in str(output or "").splitlines():
        value = str(line or "").strip()
        if not value:
            continue
        if value.startswith("ProcessId="):
            value = value.split("=", 1)[1].strip()
        if value.isdigit():
            pid_i = int(value)
            if pid_i > 0 and pid_i not in pids:
                pids.append(pid_i)
    return pids


def _list_aps_chrome_pids(profile_dir: str) -> Optional[list[int]]:
    target_profile = os.path.abspath(str(profile_dir or "").strip()) if str(profile_dir or "").strip() else ""
    if os.name != "nt":
        return []
    if not target_profile:
        return []
    rc, output = _run_powershell_text(_chrome_pid_query_script(target_profile), timeout_s=8.0)
    if rc is None or rc != 0:
        return None
    return _parse_chrome_pid_output(output)


def _stop_aps_chrome_with_result(profile_dir: str | None) -> _StopChromeResult:
    target_profile = str(profile_dir or "").strip()
    if not target_profile:
        return _StopChromeResult(True, "profile_missing", target_profile, [], [], [])
    pids = _list_aps_chrome_pids(target_profile)
    if pids is None:
        return _StopChromeResult(False, "process_list_unavailable", target_profile, [], [], [], "list_failed")
    failed_pids = [int(pid) for pid in pids if not _kill_runtime_pid(pid)]
    remaining_pids = _list_aps_chrome_pids(target_profile)
    if remaining_pids is None:
        return _StopChromeResult(False, "final_recheck_unavailable", target_profile, list(pids), [], failed_pids, "recheck_failed")
    if remaining_pids:
        return _StopChromeResult(False, "profile_processes_still_running", target_profile, list(pids), list(remaining_pids), failed_pids)
    return _StopChromeResult(True, "stopped", target_profile, list(pids), [], failed_pids)


def stop_aps_chrome_processes(profile_dir: str | None, logger: logging.Logger | None = None) -> bool:
    result = _stop_aps_chrome_with_result(profile_dir)
    if not result.ok and logger is not None:
        _log_chrome_stop_failure(result, logger=logger)
    return result.ok


def _log_chrome_stop_failure(result: _StopChromeResult, *, logger: logging.Logger | None) -> None:
    message = (
        f"chrome_stop_failed status={result.status} profile={result.profile_dir} "
        f"pids={result.pids} failed_pids={result.failed_pids} remaining_pids={result.remaining_pids}"
    )
    if logger is not None:
        try:
            logger.warning(message)
        except Exception:
            pass
        return
    print(message, file=sys.stderr)


def _stop_aps_chrome_if_requested(
    stop_aps_chrome: bool,
    profile_dir: str | None,
    *,
    logger: logging.Logger | None = None,
) -> _StopChromeResult:
    if not stop_aps_chrome:
        return _StopChromeResult(True, "not_requested", str(profile_dir or "").strip(), [], [], [])
    result = _stop_aps_chrome_with_result(profile_dir)
    if not result.ok:
        _log_chrome_stop_failure(result, logger=logger)
    return result


def _read_runtime_endpoint_files(state_dir: str) -> Dict[str, Any]:
    host_path, port_path, _db_path, _contract_path = state_contract_paths(state_dir)
    host = _read_text_file(host_path) if os.path.exists(host_path) else ""
    port = _read_port_file(port_path) if os.path.exists(port_path) else 0
    return {
        "host": host,
        "port": port,
        "host_exists": os.path.exists(host_path),
        "port_exists": os.path.exists(port_path),
    }


def _read_text_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return (f.read() or "").strip()
    except Exception:
        return ""


def _read_port_file(path: str) -> int:
    try:
        return int(_read_text_file(path))
    except Exception:
        return 0


def _runtime_identity(contract: Optional[Dict[str, Any]], lock_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract_pid = _safe_int((contract or {}).get("pid"))
    lock_pid = _safe_int((lock_payload or {}).get("pid"))
    expected_exe_path = str((contract or {}).get("exe_path") or (lock_payload or {}).get("exe_path") or "").strip()
    pid = contract_pid if contract_pid > 0 else lock_pid
    pid_match = _runtime_pid_match(contract_pid, lock_pid, expected_exe_path)
    return {
        "contract_pid": contract_pid,
        "lock_pid": lock_pid,
        "pid": pid,
        "pid_exists": bool(pid > 0 and _pid_exists(pid)),
        "pid_match": pid_match,
        "expected_exe_path": expected_exe_path,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _runtime_pid_match(contract_pid: int, lock_pid: int, expected_exe_path: str) -> Optional[bool]:
    if contract_pid > 0 and expected_exe_path:
        return _pid_matches_contract(contract_pid, expected_exe_path)
    if lock_pid > 0 and expected_exe_path:
        return _pid_matches_contract(lock_pid, expected_exe_path)
    return None


def _endpoint_status(contract: Optional[Dict[str, Any]], endpoint_files: Dict[str, Any]) -> Dict[str, Any]:
    contract_host = str((contract or {}).get("host") or "").strip()
    contract_port = _safe_int((contract or {}).get("port"))
    host = contract_host or str(endpoint_files.get("host") or "").strip() or "127.0.0.1"
    port = contract_port if contract_port > 0 else int(endpoint_files.get("port") or 0)
    endpoint_up = bool(host and int(port or 0) > 0 and _probe_runtime_health(host, int(port), timeout_s=0.75))
    return {"host": host, "port": int(port or 0), "endpoint_up": endpoint_up}


def _has_runtime_artifacts(paths: Dict[str, str]) -> bool:
    artifact_paths = (
        paths["host_path"],
        paths["port_path"],
        paths["db_path"],
        paths["contract_path"],
        paths["lock_path"],
        paths["error_path"],
    )
    return any(os.path.exists(path) for path in artifact_paths)


def _runtime_state_name(
    *,
    endpoint_up: bool,
    contract: Optional[Dict[str, Any]],
    identity: Dict[str, Any],
    lock_active: bool,
    has_artifacts: bool,
) -> str:
    contract_pid = int(identity.get("contract_pid") or 0)
    contract_mismatch = contract is not None and contract_pid > 0 and (
        identity.get("pid_exists") is False or identity.get("pid_match") is False
    )
    if endpoint_up:
        return "mixed" if contract_mismatch else "active"
    if contract_pid > 0 and bool(identity.get("pid_exists")) and identity.get("pid_match") is not False:
        return "mixed"
    if lock_active:
        return "mixed"
    if has_artifacts:
        return "stale"
    return "absent"


def _classify_runtime_state(runtime_dir_or_state_dir: str) -> Dict[str, Any]:
    runtime_dir_abs, state_dir = resolve_runtime_stop_context(runtime_dir_or_state_dir)
    paths = resolve_runtime_state_paths(state_dir)
    endpoint_files = _read_runtime_endpoint_files(state_dir)
    contract = read_runtime_contract(state_dir)
    lock_payload = read_runtime_lock(state_dir)
    identity = _runtime_identity(contract, lock_payload)
    endpoint = _endpoint_status(contract, endpoint_files)
    lock_active = bool(lock_payload and _is_runtime_lock_active(lock_payload, expected_exe_path=identity["expected_exe_path"]))
    has_artifacts = _has_runtime_artifacts(paths)
    state = _runtime_state_name(
        endpoint_up=bool(endpoint["endpoint_up"]),
        contract=contract,
        identity=identity,
        lock_active=lock_active,
        has_artifacts=has_artifacts,
    )
    return {
        "runtime_dir": runtime_dir_abs,
        "state_dir": state_dir,
        "paths": paths,
        "contract": contract,
        "lock": lock_payload,
        "host": endpoint["host"],
        "port": endpoint["port"],
        "endpoint_up": endpoint["endpoint_up"],
        "pid": int(identity["pid"] or 0),
        "pid_exists": identity["pid_exists"],
        "pid_match": identity["pid_match"],
        "lock_active": lock_active,
        "expected_exe_path": identity["expected_exe_path"],
        "chrome_profile_dir": str((contract or {}).get("chrome_profile_dir") or "").strip(),
        "has_artifacts": has_artifacts,
        "state": state,
    }


def _runtime_stop_is_complete(status: Dict[str, Any]) -> bool:
    state = str(status.get("state") or "").strip()
    if state == "absent":
        return True
    return state == "stale" and not bool(status.get("endpoint_up"))


def _can_force_kill_runtime(status: Dict[str, Any]) -> bool:
    contract = status.get("contract")
    if not isinstance(contract, dict):
        return False
    if str(status.get("state") or "") != "active" or not bool(status.get("endpoint_up")):
        return False
    pid = _safe_int(status.get("pid"))
    if pid <= 0:
        return False
    pid_match = status.get("pid_match")
    if pid_match is True:
        return True
    if pid_match is False:
        return False
    expected_exe_path = str(status.get("expected_exe_path") or "").strip()
    helper_exe_path = os.path.normcase(os.path.abspath(str(sys.executable or "").strip()))
    expected_exe_norm = os.path.normcase(os.path.abspath(expected_exe_path)) if expected_exe_path else ""
    return bool(expected_exe_norm and expected_exe_norm == helper_exe_path)


def _runtime_stop_failure_reason(status: Dict[str, Any], *, shutdown_requested: bool) -> str:
    if status.get("pid_match") is False:
        return "pid_mismatch"
    if str(status.get("state") or "") == "mixed":
        return "mixed_state"
    if bool(status.get("endpoint_up")):
        if not shutdown_requested and isinstance(status.get("contract"), dict):
            return "shutdown_request_failed"
        return "health_still_up"
    return "mixed_state"


def _runtime_process_inactive(pid: int, pid_match_hint: Optional[bool] = None) -> bool:
    pid_text = str(pid or "").strip()
    if not pid_text:
        return True
    pid_digits = pid_text[1:] if pid_text.startswith("-") else pid_text
    if not pid_digits.isdigit():
        return True
    pid_i = int(pid_text)
    if pid_i <= 0 or pid_match_hint is False:
        return True
    if not _pid_exists(pid_i):
        return True
    return False


def _finalize_stopped_runtime(status: Dict[str, Any], runtime_dir_abs: str, *, stop_aps_chrome: bool, logger) -> int:
    delete_runtime_contract_files(str(status.get("state_dir") or ""))
    profile_dir = str(status.get("chrome_profile_dir") or "").strip() or default_chrome_profile_dir(runtime_dir_abs)
    chrome_result = _stop_aps_chrome_if_requested(stop_aps_chrome, profile_dir, logger=logger)
    return 0 if chrome_result.ok else 1


def stop_runtime_from_dir(
    runtime_dir: str,
    *,
    stop_aps_chrome: bool = False,
    timeout_s: float = 15.0,
    logger: logging.Logger | None = None,
) -> int:
    runtime_dir_abs, state_dir = resolve_runtime_stop_context(runtime_dir)
    status = _classify_runtime_state(state_dir)
    if _runtime_stop_is_complete(status):
        return _finalize_stopped_runtime(status, runtime_dir_abs, stop_aps_chrome=stop_aps_chrome, logger=logger)

    grace_deadline = time.time() + max(min(float(timeout_s), 12.0), 2.0)
    shutdown_requested = _request_runtime_shutdown(status["contract"], timeout_s=3.0) if isinstance(status.get("contract"), dict) else False
    status = _wait_for_runtime_stop(state_dir, grace_deadline)
    if _runtime_stop_is_complete(status):
        return _finalize_stopped_runtime(status, runtime_dir_abs, stop_aps_chrome=stop_aps_chrome, logger=logger)

    status = _try_force_kill_runtime(state_dir, status)
    if _runtime_stop_is_complete(status):
        return _finalize_stopped_runtime(status, runtime_dir_abs, stop_aps_chrome=stop_aps_chrome, logger=logger)

    _log_runtime_stop_failure(status, shutdown_requested=shutdown_requested, logger=logger)
    return 1


def _wait_for_runtime_stop(state_dir: str, deadline: float) -> Dict[str, Any]:
    status = _classify_runtime_state(state_dir)
    while time.time() < deadline:
        status = _classify_runtime_state(state_dir)
        if _runtime_stop_is_complete(status):
            return status
        time.sleep(0.25)
    return status


def _try_force_kill_runtime(state_dir: str, status: Dict[str, Any]) -> Dict[str, Any]:
    if not _can_force_kill_runtime(status):
        return status
    _ = _kill_runtime_pid(int(status.get("pid") or 0))
    kill_deadline = time.time() + 6.0
    return _wait_for_runtime_stop(state_dir, kill_deadline)


def _log_runtime_stop_failure(status: Dict[str, Any], *, shutdown_requested: bool, logger: logging.Logger | None) -> None:
    reason = _runtime_stop_failure_reason(status, shutdown_requested=shutdown_requested)
    if logger is None:
        return
    try:
        logger.warning(
            "运行时停止失败：reason=%s state=%s shutdown_requested=%s pid=%s pid_exists=%s pid_match=%s host=%s port=%s endpoint_up=%s lock_active=%s",
            reason,
            status.get("state"),
            shutdown_requested,
            status.get("pid"),
            status.get("pid_exists"),
            status.get("pid_match"),
            status.get("host"),
            status.get("port"),
            status.get("endpoint_up"),
            status.get("lock_active"),
        )
    except Exception:
        pass
