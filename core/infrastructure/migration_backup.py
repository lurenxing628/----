from __future__ import annotations

import gc
import logging
import os
import shutil
import time

from .migrations.common import fallback_log

_LOGGER = logging.getLogger(__name__)


def is_windows_lock_error(exc: Exception) -> bool:
    try:
        if isinstance(exc, PermissionError):
            return True
        winerr = getattr(exc, "winerror", None)
        if winerr in (32, 33, 5):
            return True
    except Exception as detect_error:
        _LOGGER.debug("判断 Windows 文件锁异常失败，按非文件锁处理：%s", detect_error)
    return False


def cleanup_sqlite_sidecars(db_path: str, logger=None) -> None:
    # WAL/SHM/JOURNAL 残留可能导致“恢复后仍读到旧数据”或打开失败；最佳努力清理
    for suffix in ("-wal", "-shm", "-journal"):
        path = f"{db_path}{suffix}"
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as exc:
            if logger:
                fallback_log(logger, "warning", f"清理 SQLite sidecar 失败：{exc}（path={path}）")


def restore_db_file_from_backup(
    backup_path: str,
    db_path: str,
    logger=None,
    retries: int = 6,
    base_delay_s: float = 0.2,
) -> None:
    backup_abs = os.path.abspath(backup_path)
    db_abs = os.path.abspath(db_path)
    tmp_path = f"{db_abs}.rollback_tmp"
    last = None
    retry_count = int(retries) if retries is not None else 1
    if retry_count < 1:
        retry_count = 1
    for attempt in range(retry_count):
        try:
            _remove_tmp_file(tmp_path)
            shutil.copy2(backup_abs, tmp_path)
            os.replace(tmp_path, db_abs)
            cleanup_sqlite_sidecars(db_abs, logger=logger)
            return
        except Exception as exc:
            last = exc
            _remove_tmp_file(tmp_path)
            _collect_garbage()
            if is_windows_lock_error(exc) and attempt < retry_count - 1:
                if logger and attempt == 0:
                    fallback_log(logger, "warning", f"数据库文件回滚遇到文件锁，准备重试：{exc}（db={db_abs}）")
                time.sleep(base_delay_s * (attempt + 1))
                continue
            raise
    if last:
        raise last


def release_sqlite_connection_reference(conn) -> None:
    try:
        del conn
    except Exception as exc:
        _LOGGER.debug("释放 SQLite 连接引用失败，继续尝试回收：%s", exc)
    _collect_garbage()


def _remove_tmp_file(tmp_path: str) -> None:
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception as exc:
        _LOGGER.warning("临时数据库文件清理失败（已继续）：%s（path=%s）", exc, tmp_path)


def _collect_garbage() -> None:
    try:
        gc.collect()
    except Exception as exc:
        _LOGGER.debug("触发垃圾回收失败（已继续）：%s", exc)
