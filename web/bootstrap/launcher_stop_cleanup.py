from __future__ import annotations

from typing import Any, Dict, Optional, cast

from .launcher_lock_result import LOCK_STATUS_MISSING, read_runtime_lock_result_from_path
from .launcher_paths import db_scope_lock_path
from .launcher_runtime_lock import lock_process_identity_fields, release_runtime_lock


def read_initial_database_lock(status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sources = [item for item in (status["lock"], status["contract"]) if item is not None]
    database = next((str(item["db_path"]).strip() for item in sources if item.get("db_path")), "")
    if not database:
        return None
    result = read_runtime_lock_result_from_path(db_scope_lock_path(database))
    if result.status == LOCK_STATUS_MISSING:
        return None
    if not result.ok:
        status["db_lock_error"] = result.reason or result.error or result.status
        return None
    payload = cast(Dict[str, Any], result.payload)
    if any(lock_process_identity_fields(source) != lock_process_identity_fields(payload) for source in sources):
        status["db_lock_error"] = "database_lock_ownership_changed"
        return None
    return payload


def read_initial_runtime_claims(status: Dict[str, Any]) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "expected_lock": status["lock"],
        "expected_contract": status["contract"],
        "expected_database_lock": read_initial_database_lock(status),
    }


def release_initial_runtime_locks(
    state_dir: str, expected_lock: Optional[Dict[str, Any]], expected_database_lock: Optional[Dict[str, Any]]
) -> bool:
    claim = dict(expected_lock) if expected_lock is not None else None
    database = ""
    if expected_database_lock is not None:
        database = str(expected_database_lock.get("db_path") or "")
        if claim is None:
            claim = {}
        claim["db_lock"] = expected_database_lock
    pid = (expected_lock or expected_database_lock or {}).get("pid")
    return claim is None or release_runtime_lock(state_dir, pid, database, expected_payload=claim)
