from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from . import launcher_chrome as _chrome
from .launcher_chrome import _StopChromeResult
from .launcher_contracts import (
    CONTRACT_STATUS_INVALID,
    CONTRACT_STATUS_MISSING,
    CONTRACT_STATUS_UNREADABLE,
    CONTRACT_STATUS_VALID,
    RuntimeContractReadResult,
    _is_runtime_lock_active,
    delete_runtime_contract_files,
    delete_runtime_contract_files_result,
    read_runtime_contract,
    read_runtime_contract_result,
    read_runtime_lock,
    read_runtime_lock_result,
)
from .launcher_endpoint_result import (
    RuntimeEndpointReadResult,
    read_runtime_endpoint_files_result,
)
from .launcher_endpoint_result import (
    read_runtime_endpoint_files as _read_runtime_endpoint_files,
)
from .launcher_health import HealthProbeResult, probe_runtime_health_result
from .launcher_lock_result import (
    LOCK_STATUS_MISSING,
    LOCK_STATUS_VALID,
    RuntimeLockReadResult,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_SHUTDOWN_PATH,
    default_chrome_profile_dir,
    resolve_runtime_state_paths,
    resolve_runtime_stop_context,
)
from .launcher_processes import (
    _kill_runtime_pid,
    _pid_exists,
    _pid_matches_contract,
    _pid_state,
    _run_powershell_text,
    set_process_log_context,
)
from .launcher_stop_cleanup import delete_runtime_contract_files_result_for_stop
from .launcher_stop_process import runtime_process_inactive
from .launcher_stop_state import _runtime_state_name, _runtime_stop_is_complete

_DEFAULT_READ_RUNTIME_CONTRACT = read_runtime_contract
_DEFAULT_READ_RUNTIME_CONTRACT_RESULT = read_runtime_contract_result
_DEFAULT_READ_RUNTIME_LOCK = read_runtime_lock
_DEFAULT_READ_RUNTIME_LOCK_RESULT = read_runtime_lock_result
_DEFAULT_DELETE_RUNTIME_CONTRACT_FILES = delete_runtime_contract_files
_DEFAULT_DELETE_RUNTIME_CONTRACT_FILES_RESULT = delete_runtime_contract_files_result


def _contract_log_kwargs(contract: Dict[str, Any]) -> Dict[str, str]:
    data_dirs = contract.get("data_dirs") or {}
    state_dir = ""
    if isinstance(data_dirs, dict):
        state_dir = str(data_dirs.get("log_dir") or "").strip()
    runtime_dir = str(contract.get("runtime_dir") or "").strip()
    return {"state_dir": state_dir, "runtime_dir": runtime_dir}


def _launcher_log_contract_warning(message: str, *args: Any, contract: Dict[str, Any]) -> None:
    log_kwargs = _contract_log_kwargs(contract)
    launcher_log_warning(
        None,
        message,
        *args,
        state_dir=log_kwargs.get("state_dir") or None,
        runtime_dir=log_kwargs.get("runtime_dir") or None,
    )


def _build_shutdown_url(contract: Dict[str, Any]) -> Optional[str]:
    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = int(contract.get("port") or 0)
    except (TypeError, ValueError) as exc:
        _launcher_log_contract_warning(
            "运行时停止端口非法，无法构造关闭地址：port=%r error=%s",
            contract.get("port"),
            exc,
            contract=contract,
        )
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
        ok = int(getattr(e, "code", 500)) < 400
        if not ok:
            _launcher_log_contract_warning("运行时关闭请求被拒绝：url=%s status=%s", url, getattr(e, "code", 500), contract=contract)
        return ok
    except Exception as exc:
        _launcher_log_contract_warning("运行时关闭请求失败：url=%s error=%s", url, exc, contract=contract)
        return False


def _probe_runtime_health(host: str, port: int, timeout_s: float = 1.5, *, log_failures: bool = False) -> bool:
    return probe_runtime_health_result(host, port, timeout_s=timeout_s, log_failures=log_failures).ok


_DEFAULT_PROBE_RUNTIME_HEALTH = _probe_runtime_health
_DEFAULT_PROBE_RUNTIME_HEALTH_RESULT = probe_runtime_health_result


def probe_runtime_health(host: str, port: int, timeout_s: float = 1.5) -> bool:
    """公开只读探针：按运行时健康接口口径探测目标实例是否健康。"""
    return _probe_runtime_health(host, port, timeout_s=timeout_s, log_failures=True)


def _chrome_pid_query_script(profile_dir: str) -> str:
    return _chrome._chrome_pid_query_script(profile_dir)


def _parse_chrome_pid_output(output: str) -> List[int]:
    return _chrome._parse_chrome_pid_output(output)


def _list_aps_chrome_pids(profile_dir: str) -> Optional[List[int]]:
    return _chrome._list_aps_chrome_pids(profile_dir, run_powershell_text=_run_powershell_text)


def _stop_aps_chrome_with_result(profile_dir: Optional[str]) -> _StopChromeResult:
    return _chrome._stop_aps_chrome_with_result(
        profile_dir,
        list_pids=_list_aps_chrome_pids,
        kill_pid=_kill_runtime_pid,
    )


def stop_aps_chrome_processes(profile_dir: Optional[str], logger: Optional[logging.Logger] = None) -> bool:
    result = _stop_aps_chrome_with_result(profile_dir)
    if not result.ok and logger is not None:
        _log_chrome_stop_failure(result, logger=logger)
    return result.ok


def _log_chrome_stop_failure(result: _StopChromeResult, *, logger: Optional[logging.Logger], state_dir: str = "") -> None:
    _chrome._log_chrome_stop_failure(result, logger=logger, state_dir=state_dir)


def _stop_aps_chrome_if_requested(
    stop_aps_chrome: bool,
    profile_dir: Optional[str],
    *,
    logger: Optional[logging.Logger] = None,
    state_dir: str = "",
) -> _StopChromeResult:
    if not stop_aps_chrome:
        return _StopChromeResult(True, "not_requested", str(profile_dir or "").strip(), [], [], [])
    result = _stop_aps_chrome_with_result(profile_dir)
    if not result.ok:
        _log_chrome_stop_failure(result, logger=logger, state_dir=state_dir)
    return result


def _runtime_identity(contract: Optional[Dict[str, Any]], lock_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract_pid = _safe_int((contract or {}).get("pid"))
    lock_pid = _safe_int((lock_payload or {}).get("pid"))
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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception as exc:
        launcher_log_warning(None, "解析运行时整数失败，已按 0 处理：value=%r error=%s", value, exc)
        return 0


def _runtime_pid_match(contract_pid: int, lock_pid: int, expected_exe_path: str) -> Optional[bool]:
    if contract_pid > 0 and expected_exe_path:
        return _pid_matches_contract(contract_pid, expected_exe_path)
    if lock_pid > 0 and expected_exe_path:
        return _pid_matches_contract(lock_pid, expected_exe_path)
    return None


def _read_contract_result_for_status(state_dir: str) -> RuntimeContractReadResult:
    if read_runtime_contract is not _DEFAULT_READ_RUNTIME_CONTRACT and read_runtime_contract_result is _DEFAULT_READ_RUNTIME_CONTRACT_RESULT:
        paths = resolve_runtime_state_paths(state_dir)
        payload = read_runtime_contract(state_dir)
        if isinstance(payload, dict):
            return RuntimeContractReadResult(
                status=CONTRACT_STATUS_VALID,
                payload=payload,
                path=paths["contract_path"],
                state_dir=state_dir,
                reason="legacy_wrapper_valid",
            )
        return RuntimeContractReadResult(
            status=CONTRACT_STATUS_MISSING,
            payload=None,
            path=paths["contract_path"],
            state_dir=state_dir,
            reason="legacy_wrapper_missing",
        )
    return read_runtime_contract_result(state_dir)


def _read_lock_result_for_status(state_dir: str) -> RuntimeLockReadResult:
    if read_runtime_lock is not _DEFAULT_READ_RUNTIME_LOCK and read_runtime_lock_result is _DEFAULT_READ_RUNTIME_LOCK_RESULT:
        paths = resolve_runtime_state_paths(state_dir)
        payload = read_runtime_lock(state_dir)
        if isinstance(payload, dict):
            return RuntimeLockReadResult(
                status=LOCK_STATUS_VALID,
                payload=payload,
                path=str(payload.get("path") or paths["lock_path"]),
                state_dir=state_dir,
                reason="legacy_wrapper_valid",
            )
        return RuntimeLockReadResult(
            status=LOCK_STATUS_MISSING,
            payload=None,
            path=paths["lock_path"],
            state_dir=state_dir,
            reason="legacy_wrapper_missing",
        )
    return read_runtime_lock_result(state_dir)


def _health_result_for_status(host: str, port: int, state_dir: str) -> HealthProbeResult:
    if _probe_runtime_health is not _DEFAULT_PROBE_RUNTIME_HEALTH and probe_runtime_health_result is _DEFAULT_PROBE_RUNTIME_HEALTH_RESULT:
        ok = bool(_probe_runtime_health(host, int(port), timeout_s=0.75))
        return HealthProbeResult(ok, f"http://{host}:{int(port)}/system/health", "" if ok else "legacy_probe_false")
    return probe_runtime_health_result(host, int(port), timeout_s=0.75, state_dir=state_dir)


def _endpoint_status(contract: Optional[Dict[str, Any]], endpoint_files: RuntimeEndpointReadResult, state_dir: str) -> Dict[str, Any]:
    contract_host = str((contract or {}).get("host") or "").strip()
    contract_port = _safe_int((contract or {}).get("port"))
    host = contract_host or endpoint_files.host or "127.0.0.1"
    port = contract_port if contract_port > 0 else int(endpoint_files.port or 0)
    if not host or int(port or 0) <= 0:
        health_result = HealthProbeResult(False, "", "missing_endpoint")
    else:
        health_result = _health_result_for_status(host, int(port), state_dir)
    return {
        "host": host,
        "port": int(port or 0),
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
    return any(os.path.exists(path) for path in artifact_paths)


def _classify_runtime_state(runtime_dir_or_state_dir: str) -> Dict[str, Any]:
    runtime_dir_abs, state_dir = resolve_runtime_stop_context(runtime_dir_or_state_dir)
    set_process_log_context(state_dir=state_dir, runtime_dir=runtime_dir_abs)
    paths = resolve_runtime_state_paths(state_dir)
    endpoint_files = read_runtime_endpoint_files_result(state_dir)
    contract_result = _read_contract_result_for_status(state_dir)
    has_artifacts = _has_runtime_artifacts(paths)
    contract_capability = contract_result.to_capability(has_runtime_artifacts=has_artifacts)
    contract = contract_result.payload if contract_result.ok else None
    lock_result = _read_lock_result_for_status(state_dir)
    lock_payload = lock_result.payload if lock_result.ok else None
    identity = _runtime_identity(contract, lock_payload)
    endpoint = _endpoint_status(contract, endpoint_files, state_dir)
    endpoint_uncertain = bool(endpoint_files.uncertain and not contract_result.ok)
    lock_unknown = lock_result.status not in {LOCK_STATUS_MISSING, LOCK_STATUS_VALID}
    lock_active = bool(lock_unknown or (lock_payload and _is_runtime_lock_active(lock_payload, expected_exe_path=identity["expected_exe_path"])))
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
        "contract_capability": contract_capability,
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
        "pid": int(identity["pid"] or 0),
        "pid_exists": identity["pid_exists"],
        "pid_match": identity["pid_match"],
        "lock_active": lock_active,
        "expected_exe_path": identity["expected_exe_path"],
        "chrome_profile_dir": str((contract or {}).get("chrome_profile_dir") or "").strip(),
        "has_artifacts": has_artifacts,
        "state": state,
    }


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
    return False


def _runtime_stop_failure_reason(status: Dict[str, Any], *, shutdown_requested: bool) -> str:
    contract_status = str(status.get("contract_status") or "")
    if contract_status in {CONTRACT_STATUS_INVALID, CONTRACT_STATUS_UNREADABLE}:
        return f"contract_{contract_status}"
    if status.get("pid_match") is False:
        return "pid_mismatch"
    if str(status.get("state") or "") == "mixed":
        return "mixed_state"
    if str(status.get("state") or "") == "blocked_endpoint":
        return "endpoint_files_uncertain"
    if bool(status.get("endpoint_up")):
        if not shutdown_requested and isinstance(status.get("contract"), dict):
            return "shutdown_request_failed"
        return "health_still_up"
    return "mixed_state"


def _runtime_process_inactive(pid: int, pid_match_hint: Optional[bool] = None) -> bool:
    return runtime_process_inactive(pid, pid_match_hint, pid_state_func=_pid_state)


def _finalize_stopped_runtime(status: Dict[str, Any], runtime_dir_abs: str, *, stop_aps_chrome: bool, logger) -> int:
    state_dir = str(status.get("state_dir") or "")
    profile_dir = str(status.get("chrome_profile_dir") or "").strip() or default_chrome_profile_dir(runtime_dir_abs)
    chrome_result = _stop_aps_chrome_if_requested(stop_aps_chrome, profile_dir, logger=logger, state_dir=state_dir)
    if not chrome_result.ok:
        return 1
    cleanup_result = delete_runtime_contract_files_result_for_stop(
        state_dir,
        delete_runtime_contract_files=delete_runtime_contract_files,
        delete_runtime_contract_files_result=delete_runtime_contract_files_result,
        default_delete_runtime_contract_files=_DEFAULT_DELETE_RUNTIME_CONTRACT_FILES,
        default_delete_runtime_contract_files_result=_DEFAULT_DELETE_RUNTIME_CONTRACT_FILES_RESULT,
    )
    if not cleanup_result.ok:
        launcher_log_warning(
            logger,
            "运行时契约相关文件未清理干净，停止命令按失败处理：failures=%s",
            [failure.path for failure in cleanup_result.failures],
            state_dir=state_dir,
            write_launch_error=True,
        )
        return 1
    return 0


def stop_runtime_from_dir(
    runtime_dir: str,
    *,
    stop_aps_chrome: bool = False,
    timeout_s: float = 15.0,
    logger: Optional[logging.Logger] = None,
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
    return _classify_runtime_state(state_dir)


def _try_force_kill_runtime(state_dir: str, status: Dict[str, Any]) -> Dict[str, Any]:
    if not _can_force_kill_runtime(status):
        return status
    killed = _kill_runtime_pid(int(status.get("pid") or 0))
    if not killed:
        launcher_log_warning(None, "运行时强制停止命令未成功，继续等待最终复查：pid=%s", status.get("pid"), state_dir=str(status.get("state_dir") or ""))
    kill_deadline = time.time() + 6.0
    return _wait_for_runtime_stop(state_dir, kill_deadline)


def _log_runtime_stop_failure(status: Dict[str, Any], *, shutdown_requested: bool, logger: Optional[logging.Logger]) -> None:
    reason = _runtime_stop_failure_reason(status, shutdown_requested=shutdown_requested)
    launcher_log_warning(
        logger,
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
        state_dir=str(status.get("state_dir") or ""),
    )
