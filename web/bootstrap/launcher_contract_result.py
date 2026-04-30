from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .launcher_observability import launcher_log_warning
from .launcher_paths import RUNTIME_CONTRACT_VERSION, resolve_runtime_state_dir_for_read
from .runtime_capabilities import CapabilityResult, available, unavailable

CONTRACT_STATUS_MISSING = "missing"
CONTRACT_STATUS_VALID = "valid"
CONTRACT_STATUS_INVALID = "invalid"
CONTRACT_STATUS_UNREADABLE = "unreadable"


@dataclass(frozen=True)
class RuntimeContractReadResult:
    status: str
    payload: Optional[Dict[str, Any]]
    path: str
    state_dir: str
    reason: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == CONTRACT_STATUS_VALID

    def to_capability(self, *, has_runtime_artifacts: bool = True) -> CapabilityResult:
        details = {"path": self.path, "status": self.status}
        if self.ok:
            return available("runtime-contract", details)
        if self.status == CONTRACT_STATUS_MISSING and not has_runtime_artifacts:
            return available("runtime-contract", details)
        reason = self.reason or self.status
        if self.error:
            details["error"] = self.error
        return unavailable("runtime-contract", reason, details)


def _runtime_contract_path(state_dir: str) -> str:
    return os.path.join(str(state_dir), "aps_runtime.json")


def read_runtime_contract_result(runtime_dir: str) -> RuntimeContractReadResult:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir)
    contract_path = _runtime_contract_path(state_dir)
    if not os.path.exists(contract_path):
        return RuntimeContractReadResult(
            status=CONTRACT_STATUS_MISSING,
            payload=None,
            path=contract_path,
            state_dir=state_dir,
            reason="contract_missing",
        )
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(
            None,
            "读取运行时契约失败，已按不可读契约处理：path=%s error=%s",
            contract_path,
            exc,
            state_dir=state_dir,
            write_launch_error=True,
        )
        return RuntimeContractReadResult(
            status=CONTRACT_STATUS_UNREADABLE,
            payload=None,
            path=contract_path,
            state_dir=state_dir,
            reason="contract_unreadable",
            error=str(exc),
        )
    normalized, reason, error = _normalize_runtime_contract_payload(payload)
    if normalized is None:
        launcher_log_warning(
            None,
            "运行时契约无效：path=%s reason=%s error=%s",
            contract_path,
            reason,
            error,
            state_dir=state_dir,
            write_launch_error=True,
        )
        return RuntimeContractReadResult(
            status=CONTRACT_STATUS_INVALID,
            payload=None,
            path=contract_path,
            state_dir=state_dir,
            reason=reason or "contract_invalid",
            error=error,
        )
    return RuntimeContractReadResult(
        status=CONTRACT_STATUS_VALID,
        payload=normalized,
        path=contract_path,
        state_dir=state_dir,
    )


def _normalize_runtime_contract_payload(payload: Any) -> Tuple[Optional[Dict[str, Any]], str, str]:
    if not isinstance(payload, dict):
        return None, "contract_not_object", ""
    normalized = dict(payload)
    try:
        normalized["contract_version"] = int(normalized.get("contract_version") or 0)
    except (TypeError, ValueError) as exc:
        return None, "invalid_contract_version", str(exc)
    if normalized["contract_version"] != RUNTIME_CONTRACT_VERSION:
        return None, "contract_version_mismatch", "expected={} actual={}".format(
            RUNTIME_CONTRACT_VERSION,
            normalized["contract_version"],
        )
    for key in ("pid", "port"):
        try:
            normalized[key] = int(normalized.get(key) or 0)
        except (TypeError, ValueError) as exc:
            return None, f"invalid_{key}", str(exc)
        if int(normalized[key] or 0) <= 0:
            return None, f"invalid_{key}", "must_be_positive"
    for key in ("host", "shutdown_token", "exe_path", "runtime_dir", "chrome_profile_dir"):
        value = str(normalized.get(key) or "").strip()
        if not value:
            return None, f"missing_{key}", ""
        normalized[key] = value
    return normalized, "", ""
