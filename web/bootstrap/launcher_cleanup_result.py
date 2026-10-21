from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.safe_files import remove_fixed_file

from .launcher_contract_result import (
    CONTRACT_STATUS_MISSING,
    read_runtime_contract_result,
)
from .launcher_lock_result import LOCK_STATUS_MISSING, read_runtime_lock_result_from_path
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_ERROR_FILE,
    resolve_runtime_state_dir_for_read,
    runtime_lock_path,
    runtime_log_dir,
)
from .launcher_runtime_lock import RuntimeLockError, _lock_identity_fields, runtime_lock_mutation_guard

_MIRROR_CONTRACT_MATCH_KEYS = (
    "contract_version",
    "pid",
    "host",
    "port",
    "shutdown_token",
    "exe_path",
    "runtime_dir",
    "owner",
    "started_at",
    "db_path",
    "instance_id",
)


@dataclass(frozen=True)
class RuntimeCleanupFailure:
    path: str
    reason: str
    error: str = ""


@dataclass(frozen=True)
class RuntimeCleanupResult:
    state_dir: str
    target_dirs: Tuple[str, ...]
    attempted_paths: Tuple[str, ...]
    removed_paths: Tuple[str, ...]
    missing_paths: Tuple[str, ...]
    failures: Tuple[RuntimeCleanupFailure, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def delete_runtime_contract_files_result(
    runtime_dir: str,
    *,
    expected_lock: Optional[Dict[str, Any]],
    expected_contract: Optional[Dict[str, Any]],
) -> RuntimeCleanupResult:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir)
    target_dirs, discovery_failures = _runtime_contract_log_dirs_result(state_dir, expected_contract)
    attempted_paths: List[str] = []
    removed_paths: List[str] = []
    missing_paths: List[str] = []
    failures: List[RuntimeCleanupFailure] = list(discovery_failures)

    for log_dir in target_dirs:
        try:
            with runtime_lock_mutation_guard(runtime_lock_path(log_dir)):
                failure = _cleanup_ownership_failure(log_dir, expected_lock, expected_contract)
                if failure is not None:
                    failures.append(failure)
                    if log_dir == target_dirs[0]:
                        break
                    continue
                _remove_contract_artifacts(log_dir, attempted_paths, removed_paths, missing_paths, failures)
        except RuntimeLockError as exc:
            failures.append(RuntimeCleanupFailure(path=runtime_lock_path(log_dir), reason="mutation_guard_failed", error=str(exc)))
            if log_dir == target_dirs[0]:
                break

    return RuntimeCleanupResult(
        state_dir=state_dir,
        target_dirs=tuple(target_dirs),
        attempted_paths=tuple(attempted_paths),
        removed_paths=tuple(removed_paths),
        missing_paths=tuple(missing_paths),
        failures=tuple(failures),
    )


def _cleanup_ownership_failure(
    log_dir: str,
    expected_lock: Optional[Dict[str, Any]],
    expected_contract: Optional[Dict[str, Any]],
) -> Optional[RuntimeCleanupFailure]:
    lock_result = read_runtime_lock_result_from_path(runtime_lock_path(log_dir), state_dir=log_dir)
    if lock_result.status != LOCK_STATUS_MISSING:
        if not lock_result.ok:
            return RuntimeCleanupFailure(lock_result.path, "ownership_unavailable", lock_result.reason or lock_result.error)
        if expected_lock is None or _lock_identity_fields(lock_result.payload or {}) != _lock_identity_fields(expected_lock):
            return RuntimeCleanupFailure(lock_result.path, "ownership_changed", "运行时锁归属已变化，已保留当前实例文件。")
    contract_result = read_runtime_contract_result(log_dir)
    if contract_result.status != CONTRACT_STATUS_MISSING:
        if not contract_result.ok:
            return RuntimeCleanupFailure(contract_result.path, "ownership_unavailable", contract_result.reason or contract_result.error)
        if expected_contract is None or not _contracts_match(contract_result.payload or {}, expected_contract):
            return RuntimeCleanupFailure(contract_result.path, "ownership_changed", "运行时契约归属已变化，已保留当前实例文件。")
    if expected_lock is None and expected_contract is None and any(os.path.lexists(path) for path in _cleanup_paths(log_dir)):
        return RuntimeCleanupFailure(runtime_lock_path(log_dir), "ownership_unavailable", "缺少原实例身份，已保留运行时文件。")
    return None


def _remove_contract_artifacts(
    log_dir: str,
    attempted_paths: List[str],
    removed_paths: List[str],
    missing_paths: List[str],
    failures: List[RuntimeCleanupFailure],
) -> None:
    for path in _cleanup_paths(log_dir):
        attempted_paths.append(path)
        try:
            removed = remove_fixed_file(path, allow_symlink=False)
        except Exception as exc:
            launcher_log_warning(None, "删除运行时契约相关文件失败：path=%s error=%s", path, exc, state_dir=log_dir)
            failures.append(RuntimeCleanupFailure(path=path, reason="remove_failed", error=str(exc)))
        else:
            (removed_paths if removed else missing_paths).append(path)


def _cleanup_paths(log_dir: str) -> Tuple[str, ...]:
    return (
        os.path.join(log_dir, "aps_runtime.json"),
        os.path.join(log_dir, "aps_port.txt"),
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_db_path.txt"),
        os.path.join(log_dir, RUNTIME_ERROR_FILE),
        os.path.join(log_dir, "launcher.log"),
    )


def _runtime_contract_log_dirs_result(
    state_dir: str, payload: Optional[Dict[str, Any]]
) -> Tuple[Tuple[str, ...], Tuple[RuntimeCleanupFailure, ...]]:
    log_dirs: List[str] = [os.path.abspath(state_dir)]
    failures: List[RuntimeCleanupFailure] = []
    contract_path = os.path.join(state_dir, "aps_runtime.json")
    if payload is None:
        return tuple(log_dirs), tuple(failures)

    _append_runtime_log_dir(log_dirs, payload, failures, contract_path)
    data_dirs = payload.get("data_dirs") or {}
    if isinstance(data_dirs, dict):
        _append_mirror_log_dir(
            log_dirs,
            data_dirs.get("log_dir"),
            payload=payload,
            failures=failures,
            contract_path=contract_path,
            source_label="data_dirs.log_dir",
        )
    elif data_dirs:
        failures.append(RuntimeCleanupFailure(path=contract_path, reason="mirror_dirs_invalid", error="data_dirs_not_object"))
    return tuple(log_dirs), tuple(failures)


def _append_runtime_log_dir(
    log_dirs: List[str],
    payload: dict,
    failures: List[RuntimeCleanupFailure],
    contract_path: str,
) -> None:
    runtime_dir_s = str(payload.get("runtime_dir") or "").strip()
    if not runtime_dir_s:
        return
    _append_mirror_log_dir(
        log_dirs,
        runtime_log_dir(runtime_dir_s),
        payload=payload,
        failures=failures,
        contract_path=contract_path,
        source_label="runtime_dir.logs",
    )


def _normalize_contract_value(key: str, value: Any) -> str:
    text = str(value or "").strip()
    if key in ("exe_path", "runtime_dir", "db_path"):
        return os.path.normcase(os.path.abspath(text)) if text else ""
    return text


def _contracts_match(left: dict, right: dict) -> bool:
    for key in _MIRROR_CONTRACT_MATCH_KEYS:
        if _normalize_contract_value(key, left.get(key)) != _normalize_contract_value(key, right.get(key)):
            return False
    return True


def _matching_contract_error(mirror_log_dir_abs: str, payload: dict) -> str:
    result = read_runtime_contract_result(mirror_log_dir_abs)
    # 服务退出和停止端会先后清理同一镜像；缺失表示已清理，删除前仍会复核当前归属。
    if result.status == CONTRACT_STATUS_MISSING:
        return ""
    if not result.ok or not isinstance(result.payload, dict):
        return f"matching_contract_{result.status}:{result.reason or result.error or 'unavailable'}"
    if not _contracts_match(payload, result.payload):
        return "matching_contract_mismatch"
    return ""


def _append_mirror_log_dir(
    log_dirs: List[str],
    mirror_log_dir: Any,
    *,
    payload: dict,
    failures: List[RuntimeCleanupFailure],
    contract_path: str,
    source_label: str,
) -> None:
    mirror_log_dir_s = str(mirror_log_dir or "").strip()
    if not mirror_log_dir_s:
        return
    mirror_log_dir_abs = os.path.abspath(mirror_log_dir_s)
    existing = {os.path.normcase(path) for path in log_dirs}
    if os.path.normcase(mirror_log_dir_abs) in existing:
        return
    mirror_error = _matching_contract_error(mirror_log_dir_abs, payload)
    if mirror_error:
        failures.append(
            RuntimeCleanupFailure(
                path=contract_path,
                reason="mirror_dirs_invalid",
                error=f"{source_label}:{mirror_error}",
            )
        )
        return
    log_dirs.append(mirror_log_dir_abs)
