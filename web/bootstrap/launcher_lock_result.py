from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .launcher_observability import launcher_log_warning
from .launcher_paths import resolve_runtime_state_dir_for_read, runtime_lock_path
from .runtime_capabilities import CapabilityResult, available, unavailable

LOCK_STATUS_MISSING = "missing"
LOCK_STATUS_VALID = "valid"
LOCK_STATUS_EMPTY = "empty"
LOCK_STATUS_INVALID = "invalid"
LOCK_STATUS_UNREADABLE = "unreadable"


@dataclass(frozen=True)
class RuntimeLockReadResult:
    status: str
    payload: Optional[Dict[str, Any]]
    path: str
    state_dir: str
    reason: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == LOCK_STATUS_VALID

    def to_capability(self) -> CapabilityResult:
        details = {"path": self.path, "status": self.status}
        if self.ok or self.status == LOCK_STATUS_MISSING:
            return available("runtime-lock", details)
        if self.error:
            details["error"] = self.error
        return unavailable("runtime-lock", self.reason or self.status, details)


def _parse_key_value_lines(lines: List[str]) -> Tuple[Dict[str, str], bool]:
    data: Dict[str, str] = {}
    invalid_seen = False
    for raw in lines:
        line = str(raw or "").strip()
        if not line:
            continue
        if "=" not in line:
            invalid_seen = True
            continue
        key, value = line.split("=", 1)
        key_s = str(key or "").strip()
        if key_s:
            data[key_s] = str(value or "").strip()
    return data, invalid_seen


def read_key_value_file(path: str) -> Dict[str, str]:
    result = read_runtime_lock_result_from_path(path)
    if not result.ok:
        return {}
    payload = result.payload or {}
    return {key: str(value) for key, value in payload.items() if key not in {"pid", "state_dir", "path"}}


def read_runtime_lock_result(runtime_dir_or_state_dir: str) -> RuntimeLockReadResult:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    return read_runtime_lock_result_from_path(runtime_lock_path(state_dir), state_dir=state_dir)


def read_runtime_lock_result_from_path(path: str, *, state_dir: str = "") -> RuntimeLockReadResult:
    state_dir_s = str(state_dir or os.path.dirname(path)).strip()
    lock_path = str(path)
    if not os.path.exists(lock_path):
        return RuntimeLockReadResult(
            status=LOCK_STATUS_MISSING,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="lock_missing",
        )
    try:
        with open(lock_path, encoding="utf-8") as f:
            raw_text = f.read()
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(
            None,
            "读取运行时锁失败，跳过自动清理以避免误删：path=%s error=%s",
            lock_path,
            exc,
            state_dir=state_dir_s,
        )
        return RuntimeLockReadResult(
            status=LOCK_STATUS_UNREADABLE,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="lock_unreadable",
            error=str(exc),
        )
    if not raw_text.strip():
        return RuntimeLockReadResult(
            status=LOCK_STATUS_EMPTY,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="lock_empty",
        )
    data, invalid_seen = _parse_key_value_lines(raw_text.splitlines())
    if invalid_seen:
        return RuntimeLockReadResult(
            status=LOCK_STATUS_INVALID,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="lock_invalid_format",
        )
    if "pid" not in data:
        return RuntimeLockReadResult(
            status=LOCK_STATUS_INVALID,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="missing_pid",
        )
    payload: Dict[str, Any] = dict(data)
    try:
        payload["pid"] = int(data.get("pid") or 0)
    except (TypeError, ValueError) as exc:
        return RuntimeLockReadResult(
            status=LOCK_STATUS_INVALID,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="invalid_pid",
            error=str(exc),
        )
    if int(payload["pid"] or 0) <= 0:
        return RuntimeLockReadResult(
            status=LOCK_STATUS_INVALID,
            payload=None,
            path=lock_path,
            state_dir=state_dir_s,
            reason="invalid_pid",
            error="must_be_positive",
        )
    payload["state_dir"] = state_dir_s
    payload["path"] = lock_path
    return RuntimeLockReadResult(
        status=LOCK_STATUS_VALID,
        payload=payload,
        path=lock_path,
        state_dir=state_dir_s,
    )
