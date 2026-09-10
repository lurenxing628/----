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
    read_key_value_file,
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
    acquire_runtime_lock as acquire_runtime_lock,
)
from .launcher_runtime_lock import (
    read_runtime_lock as read_runtime_lock,
)
from .launcher_runtime_lock import (
    release_runtime_lock as release_runtime_lock,
)

_LAUNCHER_CLEANUP_API = (RuntimeCleanupFailure, RuntimeCleanupResult)


def delete_runtime_contract_files_result(runtime_dir: str) -> RuntimeCleanupResult:
    cleanup_result_mod = importlib.import_module("web.bootstrap.launcher_cleanup_result")
    return cleanup_result_mod.delete_runtime_contract_files_result(runtime_dir)


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


def write_runtime_host_port_files(
    runtime_dir: str,
    cfg_log_dir: Optional[str],
    host: str,
    port: int,
    db_path: Optional[str] = None,
    *,
    logger: Optional[logging.Logger] = None,
) -> None:
    db_for_runtime = _normalize_db_path_for_runtime(db_path)
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    _write_runtime_state_triplet(state_dir, host, port, db_for_runtime)

    mirror_log_dir = runtime_log_mirror_dir(runtime_dir, cfg_log_dir)
    if mirror_log_dir:
        try:
            os.makedirs(mirror_log_dir, exist_ok=True)
            _write_runtime_state_triplet(mirror_log_dir, host, port, db_for_runtime)
        except (OSError, TypeError, ValueError) as exc:
            safe_log(logger, "warning", "写入运行时镜像端点文件失败，主状态文件已写入：dir=%s error=%s", mirror_log_dir, exc)
    if logger is not None:
        try:
            host_file, port_file, db_file, _contract_file = state_contract_paths(state_dir)
            logger.info(f"端口已写入：{port_file} -> {int(port)}")
            logger.info(f"Host 已写入：{host_file}")
            logger.info(f"DB 路径已写入：{db_file} -> {db_for_runtime}")
        except (TypeError, ValueError) as exc:
            safe_log(logger, "warning", "记录运行时端点文件日志失败，已继续：%s", exc)


def _runtime_contract_payload(
    runtime_dir: str,
    host: str,
    port: int,
    *,
    db_path: Optional[str],
    shutdown_token: str,
    ui_mode: str,
    log_dir: Optional[str],
    backup_dir: Optional[str],
    excel_template_dir: Optional[str],
    exe_path: Optional[str] = None,
    chrome_profile_dir: Optional[str] = None,
    owner: Optional[str] = None,
) -> Dict[str, Any]:
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
    ui_mode: str,
    log_dir: Optional[str],
    backup_dir: Optional[str],
    excel_template_dir: Optional[str],
    exe_path: Optional[str] = None,
    chrome_profile_dir: Optional[str] = None,
    owner: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> str:
    payload = _runtime_contract_payload(
        runtime_dir,
        host,
        port,
        db_path=db_path,
        shutdown_token=shutdown_token,
        ui_mode=ui_mode,
        log_dir=log_dir,
        backup_dir=backup_dir,
        excel_template_dir=excel_template_dir,
        exe_path=exe_path,
        chrome_profile_dir=chrome_profile_dir,
        owner=owner,
    )
    state_dir = resolve_runtime_state_dir(runtime_dir, log_dir)
    os.makedirs(state_dir, exist_ok=True)
    contract_path = _write_runtime_contract_payload(state_dir, payload)
    mirror_log_dir = runtime_log_mirror_dir(runtime_dir, log_dir)
    if mirror_log_dir:
        try:
            os.makedirs(mirror_log_dir, exist_ok=True)
            _write_runtime_contract_payload(mirror_log_dir, payload)
        except (OSError, TypeError, ValueError) as exc:
            safe_log(logger, "warning", "写入运行时镜像契约失败，主契约已写入：dir=%s error=%s", mirror_log_dir, exc)
    if logger is not None:
        try:
            logger.info(f"运行时契约已写入：{contract_path}")
        except (TypeError, ValueError) as exc:
            safe_log(logger, "warning", "记录运行时契约日志失败，已继续：%s", exc)
    return contract_path


def _write_runtime_contract_payload(state_dir: str, payload: Dict[str, Any]) -> str:
    contract_path = _runtime_contract_path(state_dir)
    write_fixed_json(contract_path, payload, ensure_ascii=False, indent=2, sort_keys=True)
    return contract_path


def read_runtime_contract(runtime_dir: str) -> Optional[Dict[str, Any]]:
    result = read_runtime_contract_result(runtime_dir)
    return result.payload if result.ok else None


def delete_runtime_contract_files(runtime_dir: str) -> None:
    """兼容旧调用的尽力清理入口；停止链判断成功与否必须使用 result 版本。"""
    result = delete_runtime_contract_files_result(runtime_dir)
    if not result.ok:
        launcher_log_warning(
            None,
            "运行时契约兼容清理入口未清理干净，调用方如需判断成功必须改用 result 版本：failures=%s",
            [failure.path for failure in result.failures],
            state_dir=result.state_dir,
            write_launch_error=True,
        )
