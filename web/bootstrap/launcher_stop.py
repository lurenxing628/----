from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import (
    Any,
    Dict,
    Optional,
)

from .launcher_chrome import (
    _log_chrome_stop_failure,
    _stop_aps_chrome_with_result,
    _StopChromeResult,
)
from .launcher_cleanup_result import delete_runtime_contract_files_result
from .launcher_contract_result import (
    CONTRACT_STATUS_INVALID,
    CONTRACT_STATUS_UNREADABLE,
    read_runtime_contract_result,
)
from .launcher_endpoint_result import (
    RuntimeEndpointReadResult,
    read_runtime_endpoint_files_result,
)
from .launcher_health import (
    HealthProbeResult,
    probe_runtime_health_result,
)
from .launcher_lock_result import (
    LOCK_STATUS_MISSING,
    LOCK_STATUS_VALID,
    read_runtime_lock_result,
)
from .launcher_observability import (
    launcher_log_warning,
)
from .launcher_paths import (
    RUNTIME_SHUTDOWN_PATH,
    default_chrome_profile_dir,
    resolve_runtime_state_paths,
    resolve_runtime_stop_context,
)
from .launcher_processes import (
    _pid_matches_contract,
    _pid_state,
    set_process_log_context,
)
from .launcher_runtime_lock import is_runtime_lock_active
from .launcher_shutdown import HOST_STOP_PATH
from .launcher_stop_cleanup import (
    read_initial_runtime_claims,
    release_initial_runtime_locks,
)
from .launcher_stop_state import (
    _runtime_state_name,
    _runtime_stop_is_complete,
)

_STOP_GRACE_SECONDS = 12.0


def _contract_log_kwargs(contract: Dict[str, Any]) -> Dict[str, str]:
    data_dirs = contract.get("data_dirs") or {}
    state_dir = ""
    if isinstance(data_dirs, dict):
        state_dir = str(data_dirs.get("log_dir") or "").strip()
    return {"state_dir": state_dir, "runtime_dir": contract["runtime_dir"]}


def _launcher_log_contract_warning(message: str, *args: Any, contract: Dict[str, Any]) -> None:
    log_kwargs = _contract_log_kwargs(contract)
    launcher_log_warning(
        None,
        message,
        *args,
        state_dir=log_kwargs["state_dir"] or None,
        runtime_dir=log_kwargs["runtime_dir"],
    )


def _build_shutdown_url(contract: Dict[str, Any]) -> str:
    host = contract["host"]
    port = contract["port"]
    shutdown_path = str(contract.get("shutdown_path") or RUNTIME_SHUTDOWN_PATH).strip() or RUNTIME_SHUTDOWN_PATH
    if not shutdown_path.startswith("/"):
        shutdown_path = "/" + shutdown_path
    return f"http://{host}:{port}{shutdown_path}"


def _request_runtime_shutdown(contract: Dict[str, Any], timeout_s: float = 3.0) -> bool:
    url = _build_shutdown_url(contract)
    req = urllib.request.Request(url, method="POST", data=b"")
    req.add_header("X-APS-Shutdown-Token", contract["shutdown_token"])
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.5)) as resp:
            return int(resp.status) < 400
    except urllib.error.HTTPError as e:
        if e.code == 503 and contract.get("shutdown_path") != HOST_STOP_PATH:
            # Restore deliberately blocks ordinary HTTP shutdown. Only the
            # same token and endpoint may reach the DB-free owning server stop.
            return _request_runtime_shutdown({**contract, "shutdown_path": HOST_STOP_PATH}, timeout_s)
        ok = int(e.code) < 400
        if not ok:
            _launcher_log_contract_warning("运行时关闭请求被拒绝：url=%s status=%s", url, e.code, contract=contract)
        return ok
    except Exception as exc:
        _launcher_log_contract_warning("运行时关闭请求失败：url=%s error=%s", url, exc, contract=contract)
        return False


def _stop_aps_chrome_if_requested(stop_aps_chrome: bool, profile_dir: str, *, state_dir: str) -> _StopChromeResult:
    if not stop_aps_chrome:
        return _StopChromeResult(True, "not_requested", profile_dir, [], [], [])
    result = _stop_aps_chrome_with_result(profile_dir)
    if not result.ok:
        _log_chrome_stop_failure(result, state_dir=state_dir)
    return result


def _runtime_identity(contract: Optional[Dict[str, Any]], lock_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract_pid = contract["pid"] if contract else 0
    lock_pid = lock_payload["pid"] if lock_payload else 0
    expected_exe_path = str((contract or {}).get("exe_path") or (lock_payload or {}).get("exe_path") or "").strip()
    pid = contract_pid if contract_pid > 0 else lock_pid
    pid_match = _runtime_pid_match(contract_pid, lock_pid, expected_exe_path)
    pid_state = _pid_state(pid) if pid > 0 else False
    return {
        "contract_pid": contract_pid,
        "lock_pid": lock_pid,
        "pid": pid,
        "pid_exists": pid_state,
        "pid_match": pid_match,
        "expected_exe_path": expected_exe_path,
    }


def _runtime_pid_match(contract_pid: int, lock_pid: int, expected_exe_path: str) -> Optional[bool]:
    if contract_pid > 0 and expected_exe_path:
        return _pid_matches_contract(contract_pid, expected_exe_path)
    if lock_pid > 0 and expected_exe_path:
        return _pid_matches_contract(lock_pid, expected_exe_path)
    return None


def _endpoint_status(contract: Optional[Dict[str, Any]], endpoint_files: RuntimeEndpointReadResult) -> Dict[str, Any]:
    contract_host = str((contract or {}).get("host") or "").strip()
    contract_port = contract["port"] if contract else 0
    host = contract_host or endpoint_files.host or "127.0.0.1"
    port = contract_port if contract_port > 0 else endpoint_files.port
    if port <= 0:
        health_result = HealthProbeResult(False, "", "missing_endpoint")
    else:
        health_result = probe_runtime_health_result(f"http://{host}:{port}", timeout_s=0.75)
    return {
        "host": host,
        "port": port,
        "endpoint_up": bool(health_result.ok),
        "health_reason": health_result.reason,
        "health_error": health_result.error,
    }


def _has_runtime_artifacts(paths: Dict[str, str]) -> bool:
    artifact_paths = (
        paths["host_path"],
        paths["port_path"],
        paths["db_path"],
        paths["contract_path"],
        paths["lock_path"],
        paths["error_path"],
    )
    return any(os.path.lexists(path) for path in artifact_paths)


def _classify_runtime_state(runtime_dir_or_state_dir: str) -> Dict[str, Any]:
    runtime_dir_abs, state_dir = resolve_runtime_stop_context(runtime_dir_or_state_dir)
    set_process_log_context(state_dir=state_dir, runtime_dir=runtime_dir_abs)
    paths = resolve_runtime_state_paths(state_dir)
    endpoint_files = read_runtime_endpoint_files_result(state_dir)
    contract_result = read_runtime_contract_result(state_dir)
    has_artifacts = _has_runtime_artifacts(paths)
    contract = contract_result.payload if contract_result.ok else None
    lock_result = read_runtime_lock_result(state_dir)
    lock_payload = lock_result.payload if lock_result.ok else None
    identity = _runtime_identity(contract, lock_payload)
    endpoint = _endpoint_status(contract, endpoint_files)
    endpoint_uncertain = bool(endpoint_files.uncertain and not contract_result.ok)
    lock_unknown = lock_result.status not in {LOCK_STATUS_MISSING, LOCK_STATUS_VALID}
    lock_active = bool(lock_unknown or (lock_payload and is_runtime_lock_active(lock_payload, expected_exe_path=identity["expected_exe_path"])))
    state = _runtime_state_name(
        endpoint_up=bool(endpoint["endpoint_up"]),
        contract=contract,
        contract_status=contract_result.status,
        identity=identity,
        lock_active=lock_active,
        has_artifacts=has_artifacts,
        endpoint_uncertain=endpoint_uncertain,
    )
    return {
        "runtime_dir": runtime_dir_abs,
        "state_dir": state_dir,
        "paths": paths,
        "contract": contract,
        "contract_result": contract_result,
        "contract_status": contract_result.status,
        "contract_reason": contract_result.reason,
        "contract_error": contract_result.error,
        "lock": lock_payload,
        "lock_status": lock_result.status,
        "lock_reason": lock_result.reason,
        "lock_error": lock_result.error,
        "host": endpoint["host"],
        "port": endpoint["port"],
        "endpoint_up": endpoint["endpoint_up"],
        "health_reason": endpoint.get("health_reason"),
        "health_error": endpoint.get("health_error"),
        "endpoint_host_status": endpoint_files.host_status,
        "endpoint_port_status": endpoint_files.port_status,
        "endpoint_host_error": endpoint_files.host_error,
        "endpoint_port_error": endpoint_files.port_error,
        "endpoint_uncertain": endpoint_uncertain,
        "pid": identity["pid"],
        "pid_exists": identity["pid_exists"],
        "pid_match": identity["pid_match"],
        "lock_active": lock_active,
        "expected_exe_path": identity["expected_exe_path"],
        "chrome_profile_dir": str((contract or {}).get("chrome_profile_dir") or "").strip(),
        "has_artifacts": has_artifacts,
        "state": state,
    }


def _runtime_stop_failure_reason(status: Dict[str, Any], *, shutdown_requested: bool) -> str:
    contract_status = status["contract_status"]
    if contract_status in {CONTRACT_STATUS_INVALID, CONTRACT_STATUS_UNREADABLE}:
        return f"contract_{contract_status}"
    if status.get("pid_match") is False:
        return "pid_mismatch"
    if status["state"] == "mixed":
        return "mixed_state"
    if status["state"] == "blocked_endpoint":
        return "endpoint_files_uncertain"
    if bool(status.get("endpoint_up")):
        if not shutdown_requested and isinstance(status.get("contract"), dict):
            return "shutdown_request_failed"
        return "health_still_up"
    return "mixed_state"


def _finalize_stopped_runtime(
    status: Dict[str, Any], runtime_dir_abs: str, *, stop_aps_chrome: bool,
    expected_lock: Optional[Dict[str, Any]], expected_contract: Optional[Dict[str, Any]],
    expected_database_lock: Optional[Dict[str, Any]], database: str,
) -> int:
    state_dir = status["state_dir"]
    if status.get("db_lock_error"):
        launcher_log_warning(None, "原数据库运行锁归属无法确认，已保留当前锁：%s", status["db_lock_error"], state_dir=state_dir)
        return 1
    if expected_contract is None:
        profile_dir = default_chrome_profile_dir(runtime_dir_abs)
    else:
        profile_dir = expected_contract["chrome_profile_dir"]
    chrome_result = _stop_aps_chrome_if_requested(stop_aps_chrome, profile_dir, state_dir=state_dir)
    if not chrome_result.ok:
        return 1
    cleanup_result = delete_runtime_contract_files_result(
        state_dir, expected_lock=expected_lock, expected_contract=expected_contract
    )
    if not cleanup_result.ok:
        launcher_log_warning(
            None,
            "运行时契约相关文件未清理干净，停止命令按失败处理：failures=%s",
            [failure.path for failure in cleanup_result.failures],
            state_dir=state_dir,
        )
        return 1
    return 0 if release_initial_runtime_locks(state_dir, expected_lock, expected_database_lock, database) else 1


def stop_runtime_from_dir(
    runtime_dir: str,
    *,
    stop_aps_chrome: bool = False,
) -> int:
    status = _classify_runtime_state(runtime_dir)
    runtime_dir_abs = status["runtime_dir"]
    state_dir = status["state_dir"]
    original_status = status
    expected = read_initial_runtime_claims(status)
    if _runtime_stop_is_complete(status):
        return _finalize_stopped_runtime(original_status, runtime_dir_abs, stop_aps_chrome=stop_aps_chrome, **expected)

    grace_deadline = time.time() + _STOP_GRACE_SECONDS
    shutdown_requested = _request_runtime_shutdown(status["contract"], timeout_s=3.0) if isinstance(status.get("contract"), dict) else False
    status = _wait_for_runtime_stop(state_dir, grace_deadline)
    if _runtime_stop_is_complete(status):
        return _finalize_stopped_runtime(original_status, runtime_dir_abs, stop_aps_chrome=stop_aps_chrome, **expected)

    # 关闭请求受理或 HTTP 不再响应，都不能证明后台计算、写入和退出备份已结束。
    # 普通 stop 到期只报告未退出，不能自动强杀或清理仍被占用的运行时。
    _log_runtime_stop_failure(status, shutdown_requested=shutdown_requested)
    return 1


def _wait_for_runtime_stop(state_dir: str, deadline: float) -> Dict[str, Any]:
    while time.time() < deadline:
        status = _classify_runtime_state(state_dir)
        if _runtime_stop_is_complete(status):
            return status
        time.sleep(0.25)
    return _classify_runtime_state(state_dir)


def _log_runtime_stop_failure(status: Dict[str, Any], *, shutdown_requested: bool) -> None:
    reason = _runtime_stop_failure_reason(status, shutdown_requested=shutdown_requested)
    launcher_log_warning(
        None,
        "停止等待已结束，运行时尚未确认退出；未自动强制终止或清理。请稍后重试停止命令并查看运行时日志。"
        "runtime_stop_failed reason=%s state=%s shutdown_requested=%s pid=%s pid_exists=%s pid_match=%s host=%s port=%s endpoint_up=%s lock_active=%s",
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
        state_dir=status["state_dir"],
    )
