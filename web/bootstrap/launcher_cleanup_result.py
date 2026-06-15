from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Tuple

from core.infrastructure.safe_files import remove_fixed_file

from .launcher_contract_result import (
    CONTRACT_STATUS_MISSING,
    read_runtime_contract_result,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_ERROR_FILE,
    RUNTIME_LOCK_FILE,
    resolve_runtime_state_dir_for_read,
    runtime_log_dir,
)

_MIRROR_CONTRACT_MATCH_KEYS = (
    "contract_version",
    "pid",
    "host",
    "port",
    "shutdown_token",
    "exe_path",
    "runtime_dir",
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


def delete_runtime_contract_files_result(runtime_dir: str) -> RuntimeCleanupResult:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir)
    target_dirs, discovery_failures = _runtime_contract_log_dirs_result(state_dir)
    attempted_paths: List[str] = []
    removed_paths: List[str] = []
    missing_paths: List[str] = []
    failures: List[RuntimeCleanupFailure] = list(discovery_failures)

    for path in _cleanup_paths(target_dirs):
        attempted_paths.append(path)
        try:
            removed = remove_fixed_file(path, allow_symlink=False)
        except FileNotFoundError:
            missing_paths.append(path)
        except Exception as exc:
            launcher_log_warning(
                None,
                "删除运行时契约相关文件失败：path=%s error=%s",
                path,
                exc,
                state_dir=state_dir,
                write_launch_error=True,
            )
            failures.append(RuntimeCleanupFailure(path=path, reason="remove_failed", error=str(exc)))
        else:
            if removed:
                removed_paths.append(path)
            else:
                missing_paths.append(path)

    return RuntimeCleanupResult(
        state_dir=state_dir,
        target_dirs=tuple(target_dirs),
        attempted_paths=tuple(attempted_paths),
        removed_paths=tuple(removed_paths),
        missing_paths=tuple(missing_paths),
        failures=tuple(failures),
    )


def _cleanup_paths(target_dirs: Tuple[str, ...]) -> Tuple[str, ...]:
    paths: List[str] = []
    for log_dir in target_dirs:
        paths.extend(
            [
                os.path.join(log_dir, "aps_runtime.json"),
                os.path.join(log_dir, "aps_port.txt"),
                os.path.join(log_dir, "aps_host.txt"),
                os.path.join(log_dir, "aps_db_path.txt"),
                os.path.join(log_dir, RUNTIME_LOCK_FILE),
                os.path.join(log_dir, RUNTIME_ERROR_FILE),
                os.path.join(log_dir, "launcher.log"),
            ]
        )
    return tuple(paths)


def _runtime_contract_log_dirs_result(state_dir: str) -> Tuple[Tuple[str, ...], Tuple[RuntimeCleanupFailure, ...]]:
    log_dirs: List[str] = [os.path.abspath(state_dir)]
    failures: List[RuntimeCleanupFailure] = []
    contract_path = os.path.join(state_dir, "aps_runtime.json")
    result = read_runtime_contract_result(state_dir)
    if result.status == CONTRACT_STATUS_MISSING:
        return tuple(log_dirs), tuple(failures)
    if not result.ok or not isinstance(result.payload, dict):
        failures.append(
            RuntimeCleanupFailure(
                path=result.path or contract_path,
                reason="mirror_dirs_invalid",
                error=result.error or result.reason or result.status,
            )
        )
        return tuple(log_dirs), tuple(failures)

    payload = result.payload

    _append_runtime_log_dir(log_dirs, state_dir, payload, failures, contract_path)
    data_dirs = payload.get("data_dirs") or {}
    if isinstance(data_dirs, dict):
        _append_mirror_log_dir(
            log_dirs,
            state_dir,
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
    state_dir: str,
    payload: dict,
    failures: List[RuntimeCleanupFailure],
    contract_path: str,
) -> None:
    runtime_dir_s = str(payload.get("runtime_dir") or "").strip()
    if not runtime_dir_s:
        return
    _append_mirror_log_dir(
        log_dirs,
        state_dir,
        runtime_log_dir(runtime_dir_s),
        payload=payload,
        failures=failures,
        contract_path=contract_path,
        source_label="runtime_dir.logs",
    )


def _normalize_contract_value(key: str, value: Any) -> str:
    text = str(value or "").strip()
    if key in ("exe_path", "runtime_dir"):
        return os.path.normcase(os.path.abspath(text)) if text else ""
    return text


def _contracts_match(left: dict, right: dict) -> bool:
    for key in _MIRROR_CONTRACT_MATCH_KEYS:
        if _normalize_contract_value(key, left.get(key)) != _normalize_contract_value(key, right.get(key)):
            return False
    return True


def _matching_contract_error(mirror_log_dir_abs: str, payload: dict) -> str:
    result = read_runtime_contract_result(mirror_log_dir_abs)
    if not result.ok or not isinstance(result.payload, dict):
        return f"matching_contract_{result.status}:{result.reason or result.error or 'unavailable'}"
    if not _contracts_match(payload, result.payload):
        return "matching_contract_mismatch"
    return ""


def _append_mirror_log_dir(
    log_dirs: List[str],
    state_dir: str,
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
    state_dir_abs = os.path.abspath(state_dir)
    if os.path.normcase(mirror_log_dir_abs) in existing or os.path.normcase(mirror_log_dir_abs) == os.path.normcase(state_dir_abs):
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
