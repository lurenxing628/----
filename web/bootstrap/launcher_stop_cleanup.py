from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from .launcher_lock_result import LOCK_STATUS_MISSING, read_runtime_lock_result_from_path
from .launcher_paths import db_scope_lock_path
from .launcher_runtime_lock import lock_process_identity_fields, release_runtime_lock


def _read_initial_database_lock(status: Dict[str, Any], sources: List[Dict[str, Any]], database: str) -> Optional[Dict[str, Any]]:
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


def read_initial_runtime_claims(status: Dict[str, Any]) -> Dict[str, Any]:
    """停止前读一次原始归属；数据库锁只在这里按 database 读取，释放时按它记录的锁路径复用。"""
    sources = [item for item in (status["lock"], status["contract"]) if item is not None]
    database = next((str(item["db_path"]).strip() for item in sources if item.get("db_path")), "")
    return {
        "expected_lock": status["lock"],
        "expected_contract": status["contract"],
        # 没有可核对的数据库锁时为 None，只释放壳锁。
        "expected_database_lock": _read_initial_database_lock(status, sources, database) if database else None,
    }


def release_initial_runtime_locks(
    state_dir: str, expected_lock: Optional[Dict[str, Any]], expected_database_lock: Optional[Dict[str, Any]]
) -> bool:
    claim = dict(expected_lock) if expected_lock is not None else None
    if expected_database_lock is not None:
        if claim is None:
            claim = {}
        claim["db_lock"] = expected_database_lock
    return claim is None or release_runtime_lock(state_dir, expected_payload=claim)
