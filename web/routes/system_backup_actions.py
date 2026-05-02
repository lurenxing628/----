from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Optional, Tuple

from core.infrastructure.backup import maintenance_window


@dataclass(frozen=True)
class RestoreBackupOutcome:
    message: str
    category: str
    result: Any = None


def run_backup_restore(
    *,
    filename: str,
    backup_path: str,
    database_path: str,
    backup_dir: Optional[str],
    manager: Any,
    logger: Any,
    ensure_schema_func: Callable[..., Any],
) -> RestoreBackupOutcome:
    with maintenance_window(database_path, logger=logger, action="restore_flow"):
        result = manager.restore(backup_path)
        if not result.ok:
            return RestoreBackupOutcome(
                message=result.message,
                category="warning" if result.code == "busy" else "error",
            )

        result, failure = _verify_restored_database(
            filename=filename,
            result=result,
            database_path=database_path,
            backup_dir=backup_dir,
            manager=manager,
            logger=logger,
            ensure_schema_func=ensure_schema_func,
        )
        if failure is not None:
            return failure

    logger.info("数据库恢复流程完成：%s", filename)
    return RestoreBackupOutcome(
        message=f"已从备份恢复，并确认数据表可以正常使用：{filename}。建议刷新页面或重新打开浏览器以加载最新数据。",
        category="success",
        result=result,
    )


def _verify_restored_database(
    *,
    filename: str,
    result: Any,
    database_path: str,
    backup_dir: Optional[str],
    manager: Any,
    logger: Any,
    ensure_schema_func: Callable[..., Any],
) -> Tuple[Any, Optional[RestoreBackupOutcome]]:
    copied_pending_verify = str(getattr(result, "code", "") or "") == "copied_pending_verify"
    before_restore_path = getattr(result, "before_restore_path", None)
    try:
        ensure_schema_func(
            database_path,
            logger,
            backup_dir=backup_dir,
        )
    except Exception:
        if copied_pending_verify:
            return result, _rollback_after_verify_failure(
                result=result,
                before_restore_path=before_restore_path,
                manager=manager,
                logger=logger,
            )
        logger.exception("恢复后 ensure_schema 失败")
        return result, RestoreBackupOutcome(
            message="数据库文件已恢复，但数据表检查没有通过。请先联系管理员排查后再继续使用。",
            category="error",
        )
    return replace(result, code="verified", message=f"数据库文件已恢复，并确认数据表可以正常使用：{filename}"), None


def _rollback_after_verify_failure(
    *,
    result: Any,
    before_restore_path: Any,
    manager: Any,
    logger: Any,
) -> RestoreBackupOutcome:
    logger.exception("恢复后结构校验失败：数据库文件已复制，但未通过 ensure_schema")
    rollback_result = manager._auto_rollback(
        before_restore_path,
        failure_subject="数据库结构校验失败",
        rolled_back_code="verify_failed_rolled_back",
        rollback_failed_code="verify_failed_rollback_failed",
    )
    if rollback_result is None:
        rollback_result = type(result)(
            ok=False,
            code="verify_failed_rollback_failed",
            message="数据库结构校验失败，且自动回滚也失败了，请立即检查日志并手动校验数据库。",
            before_restore_path=before_restore_path,
        )
    return RestoreBackupOutcome(message=rollback_result.message, category="error")
