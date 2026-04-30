from __future__ import annotations

from typing import Any, Dict, Optional

from .launcher_contracts import CONTRACT_STATUS_INVALID, CONTRACT_STATUS_UNREADABLE


def _is_bad_contract_status(contract_status: str) -> bool:
    return contract_status in {CONTRACT_STATUS_INVALID, CONTRACT_STATUS_UNREADABLE}


def _invalid_contract_still_unsafe(contract_status: str, endpoint_up: bool, lock_active: bool) -> bool:
    return _is_bad_contract_status(contract_status) and (endpoint_up or lock_active)


def _contract_pid_mismatch(contract: Optional[Dict[str, Any]], contract_pid: int, identity: Dict[str, Any]) -> bool:
    return contract is not None and contract_pid > 0 and (
        identity.get("pid_exists") is False or identity.get("pid_match") is False
    )


def _contract_pid_requires_mixed(contract_pid: int, identity: Dict[str, Any]) -> bool:
    if contract_pid <= 0:
        return False
    if identity.get("pid_exists") is None:
        return True
    return bool(identity.get("pid_exists")) and identity.get("pid_match") is not False


def _runtime_state_name(
    *,
    endpoint_up: bool,
    contract: Optional[Dict[str, Any]],
    contract_status: str,
    identity: Dict[str, Any],
    lock_active: bool,
    has_artifacts: bool,
    endpoint_uncertain: bool = False,
) -> str:
    if _invalid_contract_still_unsafe(contract_status, endpoint_up, lock_active):
        return "mixed"
    if _is_bad_contract_status(contract_status) and has_artifacts:
        return "blocked_contract"
    if endpoint_uncertain and has_artifacts:
        return "mixed" if endpoint_up else "blocked_endpoint"
    contract_pid = int(identity.get("contract_pid") or 0)
    if endpoint_up:
        return "mixed" if _contract_pid_mismatch(contract, contract_pid, identity) else "active"
    if _contract_pid_requires_mixed(contract_pid, identity):
        return "mixed"
    if lock_active:
        return "mixed"
    if has_artifacts:
        return "stale"
    return "absent"


def _runtime_stop_is_complete(status: Dict[str, Any]) -> bool:
    state = str(status.get("state") or "").strip()
    if state == "absent":
        return True
    return state == "stale" and not bool(status.get("endpoint_up"))
