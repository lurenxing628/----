from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional, cast

from core.infrastructure.logging import safe_log
from core.infrastructure.safe_files import (
    remove_fixed_file,
    write_fixed_json,
    write_fixed_text,
)
from web.runtime_host import normalize_runtime_db_path

from .launcher_cleanup_result import contracts_match
from .launcher_contract_result import (
    CONTRACT_STATUS_MISSING,
    read_runtime_contract_result,
    runtime_contract_path,
)
from .launcher_lock_result import (
    LOCK_STATUS_MISSING,
    RuntimeLockReadResult,
    read_runtime_lock_result_from_path,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_CONTRACT_VERSION,
    launch_error_path,
    resolve_runtime_state_dir,
    resolve_runtime_state_dir_for_read,
    runtime_lock_path,
    runtime_log_mirror_dir,
    state_contract_paths,
)
from .launcher_runtime_lock import (
    RuntimeLockError,
    is_runtime_lock_active,
    lock_identity_fields,
    lock_process_identity_fields,
    runtime_lock_mutation_guard,
)


def _write_runtime_state_triplet(state_dir: str, host: str, port: int, db_for_runtime: str) -> None:
    host_file, port_file, db_file, _contract_file = state_contract_paths(state_dir)
    write_fixed_text(port_file, str(port) + "\n")
    write_fixed_text(host_file, host + "\n")
    write_fixed_text(db_file, db_for_runtime + "\n")


def clear_launch_error(runtime_dir_or_state_dir: str) -> None:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    error_path = launch_error_path(state_dir)
    try:
        remove_fixed_file(error_path)
    except FileNotFoundError:
        pass
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(None, "清理启动错误文件失败，已继续：path=%s error=%s", error_path, exc, state_dir=state_dir)


def _runtime_contract_payload(
    runtime_dir: str,
    host: str,
    port: int,
    *,
    db_path: Optional[str],
    shutdown_token: str,
    instance_id: str,
    ui_mode: str,
    log_dir: str,
    backup_dir: str,
    excel_template_dir: str,
    exe_path: str,
    chrome_profile_dir: str,
    owner: str,
) -> Dict[str, Any]:
    runtime_dir_abs = os.path.abspath(str(runtime_dir))
    return {
        "contract_version": int(RUNTIME_CONTRACT_VERSION),
        "pid": int(os.getpid()),
        "host": "127.0.0.1" if host == "0.0.0.0" else host,
        "port": int(port),
        "ui_mode": ui_mode,
        "runtime_dir": runtime_dir_abs,
        "exe_path": os.path.abspath(exe_path),
        "owner": owner,
        "instance_id": instance_id,
        "shutdown_path": "/system/runtime/shutdown",
        "shutdown_token": shutdown_token,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": normalize_runtime_db_path(db_path),
        "chrome_profile_dir": os.path.abspath(chrome_profile_dir),
        "data_dirs": {
            "log_dir": os.path.abspath(str(log_dir)),
            "backup_dir": os.path.abspath(str(backup_dir)),
            "excel_template_dir": os.path.abspath(str(excel_template_dir)),
        },
    }


def write_runtime_contract_file(
    runtime_dir: str,
    host: str,
    port: int,
    *,
    db_path: Optional[str],
    shutdown_token: str,
    instance_id: str,
    ui_mode: str,
    log_dir: str,
    backup_dir: str,
    excel_template_dir: str,
    exe_path: str,
    chrome_profile_dir: str,
    owner: str,
    logger: logging.Logger,
    expected_lock: Dict[str, Any],
) -> Dict[str, Any]:
    state_dir = expected_lock["state_dir"]
    payload = _runtime_contract_payload(
        runtime_dir,
        host,
        port,
        db_path=db_path,
        shutdown_token=shutdown_token,
        instance_id=instance_id,
        ui_mode=ui_mode,
        log_dir=log_dir,
        backup_dir=backup_dir,
        excel_template_dir=excel_template_dir,
        exe_path=exe_path,
        chrome_profile_dir=chrome_profile_dir,
        owner=owner,
    )
    contract_path = _publish_runtime_contract_directory(state_dir, payload, expected_lock, primary=True)
    mirror_dirs = (resolve_runtime_state_dir(runtime_dir, log_dir), runtime_log_mirror_dir(runtime_dir, log_dir))
    seen = {os.path.normcase(state_dir)}
    for mirror in mirror_dirs:
        if not mirror:
            continue
        mirror_log_dir = os.path.abspath(mirror)
        mirror_key = os.path.normcase(mirror_log_dir)
        if mirror_key in seen:
            continue
        seen.add(mirror_key)
        try:
            _publish_runtime_contract_directory(mirror_log_dir, payload, expected_lock, primary=False)
        except (RuntimeLockError, OSError, TypeError, ValueError) as exc:
            safe_log(logger, "warning", "写入运行时镜像契约失败，主契约已写入：dir=%s error=%s", mirror_log_dir, exc)
    logger.info(f"运行时契约已写入：{contract_path}")
    return {"path": contract_path, "payload": payload}


def _write_runtime_contract_payload(state_dir: str, payload: Dict[str, Any]) -> str:
    contract_path = runtime_contract_path(state_dir)
    write_fixed_json(contract_path, payload)
    return contract_path


def _publish_runtime_contract_directory(
    state_dir: str, payload: Dict[str, Any], expected_lock: Dict[str, Any], *, primary: bool
) -> str:
    lock_path = runtime_lock_path(state_dir)
    with runtime_lock_mutation_guard(lock_path):
        lock_result = read_runtime_lock_result_from_path(lock_path, state_dir=state_dir)
        if primary:
            if (not lock_result.ok
                    or lock_identity_fields(cast(Dict[str, Any], lock_result.payload)) != lock_identity_fields(expected_lock)
                    or lock_process_identity_fields(payload) != lock_process_identity_fields(expected_lock)):
                raise RuntimeLockError("运行锁归属已变化，运行时契约发布已停止。")
        else:
            _check_mirror_publication_ownership(state_dir, lock_result, payload, expected_lock)
        _write_runtime_state_triplet(state_dir, payload["host"], payload["port"], payload["db_path"])
        return _write_runtime_contract_payload(state_dir, payload)


def _check_mirror_publication_ownership(
    state_dir: str, lock_result: RuntimeLockReadResult, payload: Dict[str, Any], expected_lock: Dict[str, Any]
) -> None:
    if lock_result.status != LOCK_STATUS_MISSING:
        if not lock_result.ok:
            raise RuntimeLockError("镜像目录运行锁归属未知，已保留现有文件。")
        current = cast(Dict[str, Any], lock_result.payload)
        if lock_identity_fields(current) != lock_identity_fields(expected_lock):
            if is_runtime_lock_active(current, local_probe_only=True):
                raise RuntimeLockError("镜像目录正由另一实例使用，已保留现有文件。")
    contract_result = read_runtime_contract_result(state_dir)
    if contract_result.status != CONTRACT_STATUS_MISSING:
        if not contract_result.ok:
            raise RuntimeLockError("镜像目录运行时契约归属未知，已保留现有文件。")
        current_contract = cast(Dict[str, Any], contract_result.payload)
        if not contracts_match(current_contract, payload) and is_runtime_lock_active(current_contract, local_probe_only=True):
            raise RuntimeLockError("镜像目录运行时契约属于另一活动实例，已保留现有文件。")
