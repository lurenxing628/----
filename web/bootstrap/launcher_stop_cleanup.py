from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .launcher_cleanup_result import RuntimeCleanupFailure, RuntimeCleanupResult
from .launcher_lock_result import LOCK_STATUS_MISSING, read_runtime_lock_result_from_path
from .launcher_observability import launcher_log_warning
from .launcher_paths import db_scope_lock_path
from .launcher_runtime_lock import _lock_process_identity_fields, release_runtime_lock


def read_initial_database_lock(status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sources = [item for item in (status.get("lock"), status.get("contract")) if isinstance(item, dict)]
    database = next((str(item.get("db_path") or "").strip() for item in sources if item.get("db_path")), "")
    if not database:
        return None
    result = read_runtime_lock_result_from_path(db_scope_lock_path(database))
    if result.status == LOCK_STATUS_MISSING:
        return None
    if not result.ok:
        status["db_lock_error"] = result.reason or result.error or result.status
        return None
    payload = result.payload or {}
    if any(_lock_process_identity_fields(source) != _lock_process_identity_fields(payload) for source in sources):
        status["db_lock_error"] = "database_lock_ownership_changed"
        return None
    return dict(payload)


def read_initial_runtime_claims(status: Dict[str, Any]) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "expected_lock": dict(status["lock"]) if isinstance(status.get("lock"), dict) else None,
        "expected_contract": dict(status["contract"]) if isinstance(status.get("contract"), dict) else None,
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


def delete_runtime_contract_files_result_for_stop(
    state_dir: str,
    *,
    expected_lock: Optional[Dict[str, Any]],
    expected_contract: Optional[Dict[str, Any]],
    delete_runtime_contract_files: Callable[..., Any],
    delete_runtime_contract_files_result: Callable[..., RuntimeCleanupResult],
    default_delete_runtime_contract_files: Callable[..., Any],
    default_delete_runtime_contract_files_result: Callable[..., RuntimeCleanupResult],
) -> RuntimeCleanupResult:
    if delete_runtime_contract_files is not default_delete_runtime_contract_files and (
        delete_runtime_contract_files_result is default_delete_runtime_contract_files_result
    ):
        cleanup_result = default_delete_runtime_contract_files_result(
            state_dir, expected_lock=expected_lock, expected_contract=expected_contract
        )
        if not cleanup_result.ok:
            return cleanup_result
        try:
            delete_runtime_contract_files(state_dir, expected_lock=expected_lock, expected_contract=expected_contract)
        except Exception as exc:
            launcher_log_warning(
                None,
                "运行时旧清理入口失败，停止命令按清理失败处理：state_dir=%s error=%s",
                state_dir,
                exc,
                state_dir=state_dir,
                write_launch_error=True,
            )
            return RuntimeCleanupResult(
                state_dir=str(state_dir),
                target_dirs=(str(state_dir),),
                attempted_paths=(),
                removed_paths=(),
                missing_paths=(),
                failures=(RuntimeCleanupFailure(path=str(state_dir), reason="legacy_cleanup_failed", error=str(exc)),),
            )
        return cleanup_result
    return delete_runtime_contract_files_result(
        state_dir, expected_lock=expected_lock, expected_contract=expected_contract
    )
