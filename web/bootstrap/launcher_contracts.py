from __future__ import annotations

import importlib
import logging
import os
import sys
import time
from typing import Any, Dict, Optional

from core.infrastructure.logging import safe_log
from core.infrastructure.safe_files import (
    remove_fixed_file,
    write_fixed_json,
    write_fixed_text,
)

from .launcher_cleanup_result import (
    RuntimeCleanupFailure,
    RuntimeCleanupResult,
    _contracts_match,
)
from .launcher_contract_result import (
    CONTRACT_STATUS_INVALID as CONTRACT_STATUS_INVALID,
)
from .launcher_contract_result import (
    CONTRACT_STATUS_MISSING as CONTRACT_STATUS_MISSING,
)
from .launcher_contract_result import (
    CONTRACT_STATUS_UNREADABLE as CONTRACT_STATUS_UNREADABLE,
)
from .launcher_contract_result import (
    CONTRACT_STATUS_VALID as CONTRACT_STATUS_VALID,
)
from .launcher_contract_result import (
    RuntimeContractReadResult as RuntimeContractReadResult,
)
from .launcher_contract_result import (
    _normalize_runtime_contract_payload as _normalize_runtime_contract_payload,
)
from .launcher_contract_result import (
    _runtime_contract_path as _runtime_contract_path,
)
from .launcher_contract_result import (
    read_runtime_contract_result as read_runtime_contract_result,
)
from .launcher_lock_result import (
    LOCK_STATUS_MISSING,
    RuntimeLockReadResult,
    read_key_value_file,
    read_runtime_lock_result_from_path,
)
from .launcher_lock_result import (
    read_runtime_lock_result as read_runtime_lock_result,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_CONTRACT_VERSION,
    _normalize_db_path_for_runtime,
    current_runtime_owner,
    default_chrome_profile_dir,
    launch_error_path,
    resolve_runtime_state_dir,
    resolve_runtime_state_dir_for_read,
    runtime_dir_from_state_dir,
    runtime_lock_path,
    runtime_log_dir,
    runtime_log_mirror_dir,
    state_contract_paths,
)

# 运行时互斥锁生命周期已按职责拆到 launcher_runtime_lock；这里保留兼容再导出
#（launcher facade、launcher_stop、既有测试均从本模块导入锁 API）。
from .launcher_runtime_lock import (
    RuntimeLockError as RuntimeLockError,
)
from .launcher_runtime_lock import (
    _is_runtime_lock_active as _is_runtime_lock_active,
)
from .launcher_runtime_lock import (
    _lock_identity_fields,
    _lock_process_identity_fields,
    runtime_lock_mutation_guard,
)
from .launcher_runtime_lock import (
    acquire_runtime_lock as acquire_runtime_lock,
)
from .launcher_runtime_lock import (
    read_runtime_lock as read_runtime_lock,
)
from .launcher_runtime_lock import (
    release_runtime_lock as release_runtime_lock,
)

_LAUNCHER_CLEANUP_API = (RuntimeCleanupFailure, RuntimeCleanupResult)


def delete_runtime_contract_files_result(
    runtime_dir: str,
    *,
    expected_lock: Optional[Dict[str, Any]],
    expected_contract: Optional[Dict[str, Any]],
) -> RuntimeCleanupResult:
    cleanup_result_mod = importlib.import_module("web.bootstrap.launcher_cleanup_result")
    return cleanup_result_mod.delete_runtime_contract_files_result(
        runtime_dir, expected_lock=expected_lock, expected_contract=expected_contract
    )


def _write_runtime_state_triplet(state_dir: str, host: str, port: int, db_for_runtime: str) -> None:
    host_file, port_file, db_file, _contract_file = state_contract_paths(state_dir)
    write_fixed_text(port_file, str(int(port)) + "\n")
    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    write_fixed_text(host_file, str(host_for_client) + "\n")
    write_fixed_text(db_file, db_for_runtime + "\n")


def _write_key_value_file(path: str, data: Dict[str, Any]) -> None:
    lines = []
    for key, value in (data or {}).items():
        key_s = str(key or "").strip()
        if not key_s:
            continue
        value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"{key_s}={value_s}")
    write_fixed_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _read_key_value_file(path: str) -> Dict[str, str]:
    return read_key_value_file(path)


def write_launch_error(runtime_dir: str, message: str, cfg_log_dir: Optional[str] = None) -> str:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    error_path = launch_error_path(state_dir)
    write_fixed_text(error_path, (str(message or "").strip() or "应用启动失败。") + "\n")
    return error_path


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
    log_dir: Optional[str],
    backup_dir: Optional[str],
    excel_template_dir: Optional[str],
    exe_path: Optional[str] = None,
    chrome_profile_dir: Optional[str] = None,
    owner: Optional[str] = None,
) -> Dict[str, Any]:
    instance_id = str(instance_id or "").strip()
    if not instance_id:
        raise ValueError("runtime instance_id is required")
    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    runtime_dir_abs = os.path.abspath(str(runtime_dir))
    return {
        "contract_version": int(RUNTIME_CONTRACT_VERSION),
        "pid": int(os.getpid()),
        "host": host_for_client,
        "port": int(port),
        "ui_mode": str(ui_mode or "").strip() or "unknown",
        "runtime_dir": runtime_dir_abs,
        "exe_path": os.path.abspath(str(exe_path or sys.executable or "")).strip(),
        "owner": str(owner or current_runtime_owner()).strip() or "unknown",
        "instance_id": instance_id,
        "shutdown_path": "/system/runtime/shutdown",
        "shutdown_token": str(shutdown_token or "").strip(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": _normalize_db_path_for_runtime(db_path),
        "chrome_profile_dir": os.path.abspath(str(chrome_profile_dir or default_chrome_profile_dir(runtime_dir_abs))),
        "data_dirs": {
            "log_dir": os.path.abspath(str(log_dir or runtime_log_dir(runtime_dir_abs))),
            "backup_dir": os.path.abspath(str(backup_dir or os.path.join(runtime_dir_abs, "backups"))),
            "excel_template_dir": os.path.abspath(
                str(excel_template_dir or os.path.join(runtime_dir_abs, "templates_excel"))
            ),
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
    log_dir: Optional[str],
    backup_dir: Optional[str],
    excel_template_dir: Optional[str],
    exe_path: Optional[str] = None,
    chrome_profile_dir: Optional[str] = None,
    owner: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    expected_lock: Dict[str, Any],
) -> Dict[str, Any]:
    state_dir_s = str((expected_lock or {}).get("state_dir") or "").strip()
    if not state_dir_s:
        raise RuntimeLockError("缺少原壳锁目录，运行时契约发布已停止。")
    state_dir = os.path.abspath(state_dir_s)
    if _normalize_db_path_for_runtime(expected_lock.get("path")) != _normalize_db_path_for_runtime(runtime_lock_path(state_dir)):
        raise RuntimeLockError("原壳锁路径与目录不一致，运行时契约发布已停止。")
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
    if logger is not None:
        try:
            logger.info(f"运行时契约已写入：{contract_path}")
        except (TypeError, ValueError) as exc:
            safe_log(logger, "warning", "记录运行时契约日志失败，已继续：%s", exc)
    return {"path": contract_path, "payload": payload}


def _write_runtime_contract_payload(state_dir: str, payload: Dict[str, Any]) -> str:
    contract_path = _runtime_contract_path(state_dir)
    write_fixed_json(contract_path, payload, ensure_ascii=False, indent=2, sort_keys=True)
    return contract_path


def _publish_runtime_contract_directory(
    state_dir: str, payload: Dict[str, Any], expected_lock: Dict[str, Any], *, primary: bool
) -> str:
    lock_path = runtime_lock_path(state_dir)
    with runtime_lock_mutation_guard(lock_path):
        lock_result = read_runtime_lock_result_from_path(lock_path, state_dir=state_dir)
        if primary:
            if (not lock_result.ok
                    or _lock_identity_fields(lock_result.payload or {}) != _lock_identity_fields(expected_lock)
                    or _lock_process_identity_fields(payload) != _lock_process_identity_fields(expected_lock)):
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
        current = lock_result.payload or {}
        if _lock_identity_fields(current) != _lock_identity_fields(expected_lock):
            if _is_runtime_lock_active(current, local_probe_only=True):
                raise RuntimeLockError("镜像目录正由另一实例使用，已保留现有文件。")
    contract_result = read_runtime_contract_result(state_dir)
    if contract_result.status != CONTRACT_STATUS_MISSING:
        if not contract_result.ok:
            raise RuntimeLockError("镜像目录运行时契约归属未知，已保留现有文件。")
        current_contract = contract_result.payload or {}
        if not _contracts_match(current_contract, payload) and _is_runtime_lock_active(current_contract, local_probe_only=True):
            raise RuntimeLockError("镜像目录运行时契约属于另一活动实例，已保留现有文件。")


def read_runtime_contract(runtime_dir: str) -> Optional[Dict[str, Any]]:
    result = read_runtime_contract_result(runtime_dir)
    return result.payload if result.ok else None


def delete_runtime_contract_files(
    runtime_dir: str,
    *,
    expected_lock: Optional[Dict[str, Any]],
    expected_contract: Optional[Dict[str, Any]],
) -> RuntimeCleanupResult:
    """兼容旧调用的尽力清理入口；停止链判断成功与否必须使用 result 版本。"""
    result = delete_runtime_contract_files_result(
        runtime_dir, expected_lock=expected_lock, expected_contract=expected_contract
    )
    if not result.ok:
        launcher_log_warning(
            None,
            "运行时契约兼容清理入口未清理干净，调用方如需判断成功必须改用 result 版本：failures=%s",
            [failure.path for failure in result.failures],
            state_dir=result.state_dir,
        )
    return result
