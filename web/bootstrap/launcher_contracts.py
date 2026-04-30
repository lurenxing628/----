from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

from core.infrastructure.logging import safe_log

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
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_CONTRACT_VERSION,
    RUNTIME_ERROR_FILE,
    RUNTIME_LOCK_FILE,
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
from .launcher_processes import _pid_matches_contract, _pid_state, set_process_log_context


class RuntimeLockError(RuntimeError):
    def __init__(self, message: str, *, owner: str = "", pid: int = 0):
        super().__init__(message)
        self.owner = str(owner or "").strip()
        try:
            self.pid = int(pid or 0)
        except (TypeError, ValueError) as exc:
            launcher_log_warning(None, "解析运行时锁 pid 失败，已按 0 处理：pid=%r error=%s", pid, exc)
            self.pid = 0


def _write_runtime_state_triplet(state_dir: str, host: str, port: int, db_for_runtime: str) -> None:
    host_file, port_file, db_file, _contract_file = state_contract_paths(state_dir)
    with open(port_file, "w", encoding="utf-8") as f:
        f.write(str(int(port)) + "\n")
    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    with open(host_file, "w", encoding="utf-8") as f:
        f.write(str(host_for_client) + "\n")
    with open(db_file, "w", encoding="utf-8") as f:
        f.write(db_for_runtime + "\n")


def _write_key_value_file(path: str, data: Dict[str, Any]) -> None:
    lines = []
    for key, value in (data or {}).items():
        key_s = str(key or "").strip()
        if not key_s:
            continue
        value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"{key_s}={value_s}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def _read_key_value_file(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    data: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(None, "读取运行时键值文件失败，已按空文件处理：path=%s error=%s", path, exc, state_dir=os.path.dirname(path))
        return {}
    for raw in lines:
        line = str(raw or "").strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key_s = str(key or "").strip()
        if key_s:
            data[key_s] = str(value or "").strip()
    return data


def read_runtime_lock(runtime_dir_or_state_dir: str) -> Optional[Dict[str, Any]]:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    lock_path = runtime_lock_path(state_dir)
    if not os.path.exists(lock_path):
        return None
    payload_raw = _read_key_value_file(lock_path)
    if not payload_raw:
        return None
    payload: Dict[str, Any] = dict(payload_raw)
    try:
        payload["pid"] = int(payload.get("pid") or 0)
    except (TypeError, ValueError) as exc:
        launcher_log_warning(None, "运行时锁 pid 非法，已按失效锁处理：path=%s error=%s", lock_path, exc, state_dir=state_dir)
        payload["pid"] = 0
    payload["state_dir"] = state_dir
    payload["path"] = lock_path
    return payload


def _is_runtime_lock_active(lock_payload: Dict[str, Any], expected_exe_path: str = "") -> bool:
    if not isinstance(lock_payload, dict):
        return False
    state_dir = str(lock_payload.get("state_dir") or "")
    set_process_log_context(state_dir=state_dir)
    try:
        pid = int(lock_payload.get("pid") or 0)
    except (TypeError, ValueError) as exc:
        launcher_log_warning(None, "运行时锁 pid 非法，已按非活跃处理：%s", exc, state_dir=str(lock_payload.get("state_dir") or ""))
        pid = 0
    if pid <= 0:
        return False
    pid_state = _pid_state(pid)
    if pid_state is False:
        return False
    if pid_state is None:
        launcher_log_warning(None, "运行时锁 pid 状态无法确认，按仍可能活跃处理：pid=%s", pid, state_dir=str(lock_payload.get("state_dir") or ""))
        return True
    exe_path = str(lock_payload.get("exe_path") or expected_exe_path or "").strip()
    if exe_path:
        pid_match = _pid_matches_contract(pid, exe_path)
        if pid_match is False:
            return False
    return True


def _runtime_lock_payload(owner: Optional[str], exe_path: Optional[str]) -> Dict[str, Any]:
    owner_s = str(owner or current_runtime_owner()).strip() or "unknown"
    exe_path_s = os.path.abspath(str(exe_path or sys.executable or "")).strip()
    return {
        "pid": int(os.getpid()),
        "owner": owner_s,
        "exe_path": exe_path_s,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _create_new_runtime_lock(lock_path: str, payload: Dict[str, Any]) -> bool:
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except Exception as e:
        raise RuntimeLockError(f"创建运行时锁失败：{e}") from e
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for key, value in payload.items():
                value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
                f.write(f"{key}={value_s}\n")
    except Exception:
        try:
            os.remove(lock_path)
        except Exception as cleanup_exc:
            launcher_log_warning(
                None,
                "创建运行时锁失败后清理锁文件失败，已继续抛出原错误：path=%s error=%s",
                lock_path,
                cleanup_exc,
                state_dir=os.path.dirname(lock_path),
            )
        raise
    return True


def _raise_if_runtime_lock_active(existing: Dict[str, Any], owner_s: str, exe_path_s: str) -> None:
    if not _is_runtime_lock_active(existing, expected_exe_path=exe_path_s):
        return
    existing_owner = str(existing.get("owner") or "").strip()
    existing_pid = int(existing.get("pid") or 0)
    if existing_owner and existing_owner != owner_s:
        raise RuntimeLockError(
            f"系统当前正由 {existing_owner} 使用，请等待其退出后再试。",
            owner=existing_owner,
            pid=existing_pid,
        ) from None
    raise RuntimeLockError(
        "系统已在当前账户运行，请直接使用现有窗口，不要重复启动。",
        owner=existing_owner or owner_s,
        pid=existing_pid,
    ) from None


def _remove_stale_runtime_lock(lock_path: str) -> None:
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass
    except Exception as e:
        raise RuntimeLockError(f"检测到失效运行时锁，但无法清理：{e}") from e


def acquire_runtime_lock(
    runtime_dir: str,
    cfg_log_dir: Optional[str] = None,
    *,
    owner: Optional[str] = None,
    exe_path: Optional[str] = None,
) -> Dict[str, Any]:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    lock_path = runtime_lock_path(state_dir)
    payload = _runtime_lock_payload(owner, exe_path)
    owner_s = str(payload.get("owner") or "unknown")
    exe_path_s = str(payload.get("exe_path") or "")
    for _ in range(2):
        if _create_new_runtime_lock(lock_path, payload):
            payload["state_dir"] = state_dir
            payload["path"] = lock_path
            return payload
        existing = read_runtime_lock(state_dir) or {}
        _raise_if_runtime_lock_active(existing, owner_s, exe_path_s)
        _remove_stale_runtime_lock(lock_path)
    raise RuntimeLockError("创建运行时锁失败，请稍后重试。")


def release_runtime_lock(runtime_dir_or_state_dir: str, expected_pid: Optional[int] = None) -> None:
    existing = read_runtime_lock(runtime_dir_or_state_dir)
    if not existing:
        return
    pid0 = int(existing.get("pid") or 0)
    state_dir = str(existing.get("state_dir") or resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir))
    if expected_pid is None:
        pid_expected = int(os.getpid())
    else:
        try:
            pid_expected = int(expected_pid)
        except (TypeError, ValueError) as exc:
            launcher_log_warning(
                None,
                "释放运行时锁时 expected_pid 非法，跳过释放以避免误删他人锁：expected_pid=%r error=%s",
                expected_pid,
                exc,
                state_dir=state_dir,
            )
            return
    if pid_expected <= 0:
        launcher_log_warning(None, "释放运行时锁时 expected_pid 非正，跳过释放：expected_pid=%s", pid_expected, state_dir=state_dir)
        return
    if pid0 > 0 and pid0 != pid_expected:
        return
    try:
        os.remove(str(existing.get("path") or ""))
    except FileNotFoundError:
        pass
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(None, "释放运行时锁失败，已继续：path=%s error=%s", existing.get("path"), exc, state_dir=state_dir)


def write_launch_error(runtime_dir: str, message: str, cfg_log_dir: Optional[str] = None) -> str:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    error_path = launch_error_path(state_dir)
    with open(error_path, "w", encoding="utf-8") as f:
        f.write((str(message or "").strip() or "应用启动失败。") + "\n")
    return error_path


def clear_launch_error(runtime_dir_or_state_dir: str) -> None:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    error_path = launch_error_path(state_dir)
    try:
        os.remove(error_path)
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
        except (TypeError, ValueError) as exc:
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
        except (TypeError, ValueError) as exc:
            safe_log(logger, "warning", "写入运行时镜像契约失败，主契约已写入：dir=%s error=%s", mirror_log_dir, exc)
    if logger is not None:
        try:
            logger.info(f"运行时契约已写入：{contract_path}")
        except (TypeError, ValueError) as exc:
            safe_log(logger, "warning", "记录运行时契约日志失败，已继续：%s", exc)
    return contract_path


def _write_runtime_contract_payload(state_dir: str, payload: Dict[str, Any]) -> str:
    contract_path = _runtime_contract_path(state_dir)
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return contract_path


def read_runtime_contract(runtime_dir: str) -> Optional[Dict[str, Any]]:
    result = read_runtime_contract_result(runtime_dir)
    return result.payload if result.ok else None


def delete_runtime_contract_files(runtime_dir: str) -> None:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir)
    log_dirs = _runtime_contract_log_dirs(state_dir)
    paths = []
    for log_dir in log_dirs:
        paths.extend(
            [
                os.path.join(log_dir, "aps_runtime.json"),
                os.path.join(log_dir, "aps_port.txt"),
                os.path.join(log_dir, "aps_host.txt"),
                os.path.join(log_dir, "aps_db_path.txt"),
                os.path.join(log_dir, RUNTIME_LOCK_FILE),
                os.path.join(log_dir, RUNTIME_ERROR_FILE),
            ]
        )
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception as exc:
            launcher_log_warning(None, "删除运行时契约相关文件失败，已继续：path=%s error=%s", path, exc, state_dir=state_dir)


def _runtime_contract_log_dirs(state_dir: str) -> List[str]:
    log_dirs = [state_dir]
    contract_path = _runtime_contract_path(state_dir)
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        launcher_log_warning(None, "读取运行时契约镜像目录失败，将只清理当前状态目录：path=%s error=%s", contract_path, exc, state_dir=state_dir)
        return log_dirs
    if not isinstance(payload, dict):
        return log_dirs
    runtime_dir_raw = str(payload.get("runtime_dir") or "").strip()
    if runtime_dir_raw:
        runtime_log_dir_abs = os.path.abspath(runtime_log_dir(runtime_dir_raw))
        if os.path.normcase(runtime_log_dir_abs) != os.path.normcase(os.path.abspath(state_dir)):
            log_dirs.append(runtime_log_dir_abs)
    data_dirs = payload.get("data_dirs") or {}
    if isinstance(data_dirs, dict):
        _append_mirror_log_dir(log_dirs, state_dir, data_dirs.get("log_dir"))
    return log_dirs


def _append_mirror_log_dir(log_dirs: List[str], state_dir: str, mirror_log_dir: Any) -> None:
    mirror_log_dir_s = str(mirror_log_dir or "").strip()
    if not mirror_log_dir_s:
        return
    mirror_log_dir_abs = os.path.abspath(mirror_log_dir_s)
    if os.path.normcase(mirror_log_dir_abs) != os.path.normcase(os.path.abspath(state_dir)):
        log_dirs.append(mirror_log_dir_abs)
