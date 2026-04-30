from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, List, Tuple

from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    RUNTIME_ERROR_FILE,
    RUNTIME_LOCK_FILE,
    resolve_runtime_state_dir_for_read,
    runtime_log_dir,
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
            os.remove(path)
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
            removed_paths.append(path)

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
            ]
        )
    return tuple(paths)


def _runtime_contract_log_dirs_result(state_dir: str) -> Tuple[Tuple[str, ...], Tuple[RuntimeCleanupFailure, ...]]:
    log_dirs: List[str] = [os.path.abspath(state_dir)]
    failures: List[RuntimeCleanupFailure] = []
    contract_path = os.path.join(state_dir, "aps_runtime.json")
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return tuple(log_dirs), tuple(failures)
    except Exception as exc:
        launcher_log_warning(
            None,
            "读取运行时契约镜像目录失败，将只清理当前状态目录：path=%s error=%s",
            contract_path,
            exc,
            state_dir=state_dir,
            write_launch_error=True,
        )
        failures.append(RuntimeCleanupFailure(path=contract_path, reason="mirror_dirs_unreadable", error=str(exc)))
        return tuple(log_dirs), tuple(failures)

    if not isinstance(payload, dict):
        failures.append(RuntimeCleanupFailure(path=contract_path, reason="mirror_dirs_invalid", error="contract_not_object"))
        return tuple(log_dirs), tuple(failures)

    _append_runtime_log_dir(log_dirs, state_dir, payload.get("runtime_dir"))
    data_dirs = payload.get("data_dirs") or {}
    if isinstance(data_dirs, dict):
        _append_mirror_log_dir(log_dirs, state_dir, data_dirs.get("log_dir"))
    elif data_dirs:
        failures.append(RuntimeCleanupFailure(path=contract_path, reason="mirror_dirs_invalid", error="data_dirs_not_object"))
    return tuple(log_dirs), tuple(failures)


def _append_runtime_log_dir(log_dirs: List[str], state_dir: str, runtime_dir_raw: Any) -> None:
    runtime_dir_s = str(runtime_dir_raw or "").strip()
    if not runtime_dir_s:
        return
    _append_mirror_log_dir(log_dirs, state_dir, runtime_log_dir(runtime_dir_s))


def _append_mirror_log_dir(log_dirs: List[str], state_dir: str, mirror_log_dir: Any) -> None:
    mirror_log_dir_s = str(mirror_log_dir or "").strip()
    if not mirror_log_dir_s:
        return
    mirror_log_dir_abs = os.path.abspath(mirror_log_dir_s)
    existing = {os.path.normcase(path) for path in log_dirs}
    if os.path.normcase(mirror_log_dir_abs) not in existing and os.path.normcase(mirror_log_dir_abs) != os.path.normcase(
        os.path.abspath(state_dir)
    ):
        log_dirs.append(mirror_log_dir_abs)
