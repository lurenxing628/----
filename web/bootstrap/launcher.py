from __future__ import annotations

from typing import Optional

from . import launcher_contracts as _contracts
from . import launcher_paths as _paths
from . import launcher_processes as _processes
from . import launcher_stop as _stop
from .launcher_contracts import (
    RuntimeCleanupFailure,
    RuntimeCleanupResult,
    RuntimeLockError,
    _is_runtime_lock_active,
    _read_key_value_file,
    _runtime_contract_path,
    _runtime_contract_payload,
    _write_key_value_file,
    _write_runtime_state_triplet,
    acquire_runtime_lock,
    clear_launch_error,
    delete_runtime_contract_files,
    delete_runtime_contract_files_result,
    read_runtime_contract,
    read_runtime_contract_result,
    read_runtime_lock,
    read_runtime_lock_result,
    release_runtime_lock,
    write_launch_error,
    write_runtime_contract_file,
    write_runtime_host_port_files,
)
from .launcher_endpoint_result import RuntimeEndpointReadResult, read_runtime_endpoint_files_result
from .launcher_network import BindProbeResult, _can_bind, _can_bind_result, pick_bind_host, pick_port
from .launcher_paths import (
    RUNTIME_CONTRACT_VERSION as _RUNTIME_CONTRACT_VERSION,
)
from .launcher_paths import (
    RUNTIME_ERROR_FILE as _RUNTIME_ERROR_FILE,
)
from .launcher_paths import (
    RUNTIME_LOCK_FILE as _RUNTIME_LOCK_FILE,
)
from .launcher_paths import (
    RUNTIME_SHUTDOWN_PATH as _RUNTIME_SHUTDOWN_PATH,
)
from .launcher_paths import (
    _compose_runtime_owner,
    _normalize_abs_dir,
    _normalize_db_path_for_runtime,
    current_runtime_owner,
    default_chrome_profile_dir,
    read_shared_data_root_from_registry,
    resolve_prelaunch_log_dir,
    resolve_runtime_state_dir,
    resolve_runtime_state_paths,
)
from .launcher_paths import (
    launch_error_path as _launch_error_path,
)
from .launcher_paths import (
    resolve_runtime_state_dir_for_read as _resolve_runtime_state_dir_for_read,
)
from .launcher_paths import (
    resolve_runtime_stop_context as _resolve_runtime_stop_context,
)
from .launcher_paths import (
    resolve_shared_data_root as _resolve_shared_data_root_impl,
)
from .launcher_paths import (
    runtime_dir_from_state_dir as _runtime_dir_from_state_dir,
)
from .launcher_paths import (
    runtime_lock_path as _runtime_lock_path,
)
from .launcher_paths import (
    runtime_log_dir as _runtime_log_dir,
)
from .launcher_paths import (
    runtime_log_mirror_dir as _runtime_log_mirror_dir,
)
from .launcher_paths import (
    state_contract_paths as _state_contract_paths,
)
from .launcher_processes import (
    _kill_runtime_pid,
    _pid_exists,
    _pid_matches_contract,
    _pid_state,
    _query_process_executable_path,
    _run_powershell_text,
    runtime_pid_exists,
    runtime_pid_matches_executable,
    runtime_pid_state,
)
from .launcher_stop import (
    _build_shutdown_url,
    _can_force_kill_runtime,
    _classify_runtime_state,
    _list_aps_chrome_pids,
    _probe_runtime_health,
    _read_runtime_endpoint_files,
    _request_runtime_shutdown,
    _runtime_process_inactive,
    _runtime_stop_failure_reason,
    _runtime_stop_is_complete,
    _stop_aps_chrome_if_requested,
    probe_runtime_health,
    probe_runtime_health_result,
)

time = _stop.time

_FACADE_RESULT_API = (
    BindProbeResult,
    RuntimeCleanupFailure,
    RuntimeCleanupResult,
    RuntimeEndpointReadResult,
    _can_bind_result,
    delete_runtime_contract_files_result,
    read_runtime_contract_result,
    read_runtime_endpoint_files_result,
    read_runtime_lock_result,
    probe_runtime_health_result,
)


def resolve_shared_data_root(base_dir: str, *, frozen: Optional[bool] = None) -> str:
    _paths.read_shared_data_root_from_registry = read_shared_data_root_from_registry
    return _resolve_shared_data_root_impl(base_dir, frozen=frozen)


def _sync_launcher_hooks(*, include_chrome_hook: bool) -> None:
    _processes._pid_exists = _pid_exists
    _processes._pid_matches_contract = _pid_matches_contract
    _processes._kill_runtime_pid = _kill_runtime_pid
    _processes._run_powershell_text = _run_powershell_text
    _contracts._pid_matches_contract = _pid_matches_contract
    _contracts._pid_state = _pid_state
    _stop._pid_exists = _pid_exists
    _stop._pid_matches_contract = _pid_matches_contract
    _stop._pid_state = _pid_state
    _stop._kill_runtime_pid = _kill_runtime_pid
    _stop._run_powershell_text = _run_powershell_text
    _stop._probe_runtime_health = _probe_runtime_health
    _stop._request_runtime_shutdown = _request_runtime_shutdown
    _stop._list_aps_chrome_pids = _list_aps_chrome_pids
    _stop.delete_runtime_contract_files = delete_runtime_contract_files
    _stop.delete_runtime_contract_files_result = delete_runtime_contract_files_result
    _stop.read_runtime_contract = read_runtime_contract
    _stop.read_runtime_contract_result = read_runtime_contract_result
    _stop.read_runtime_endpoint_files_result = read_runtime_endpoint_files_result
    _stop.read_runtime_lock = read_runtime_lock
    _stop.read_runtime_lock_result = read_runtime_lock_result
    _stop.probe_runtime_health_result = probe_runtime_health_result
    _stop.default_chrome_profile_dir = default_chrome_profile_dir
    if include_chrome_hook:
        _sync_chrome_stop_hook()
    else:
        _stop._stop_aps_chrome_with_result = _original_stop_chrome_with_result


def _sync_chrome_stop_hook() -> None:
    current_stop = globals().get("stop_aps_chrome_processes")
    if current_stop is _facade_stop_aps_chrome_processes:
        _stop._stop_aps_chrome_with_result = _original_stop_chrome_with_result
        return

    def _hooked_stop_result(profile_dir):
        ok = bool(current_stop(profile_dir, logger=None))  # type: ignore[misc]
        return _stop._StopChromeResult(
            ok,
            "facade_hook" if ok else "facade_hook_failed",
            str(profile_dir or "").strip(),
            [],
            [],
            [],
        )

    _stop._stop_aps_chrome_with_result = _hooked_stop_result


def stop_aps_chrome_processes(profile_dir: Optional[str], logger=None) -> bool:
    _sync_launcher_hooks(include_chrome_hook=False)
    return _stop.stop_aps_chrome_processes(profile_dir, logger=logger)


_facade_stop_aps_chrome_processes = stop_aps_chrome_processes
_original_stop_chrome_with_result = _stop._stop_aps_chrome_with_result


def stop_runtime_from_dir(
    runtime_dir: str,
    *,
    stop_aps_chrome: bool = False,
    timeout_s: float = 15.0,
    logger=None,
) -> int:
    _sync_launcher_hooks(include_chrome_hook=True)
    try:
        return _stop.stop_runtime_from_dir(
            runtime_dir,
            stop_aps_chrome=stop_aps_chrome,
            timeout_s=timeout_s,
            logger=logger,
        )
    finally:
        _stop._stop_aps_chrome_with_result = _original_stop_chrome_with_result
