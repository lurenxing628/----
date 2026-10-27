"""Shared SQLite integrity checks for backup creation and restoration."""

from __future__ import annotations

from .migration_common import fallback_log


class BackupIntegrityError(RuntimeError):
    """备份/恢复源文件损坏、缺少业务表，或完整性校验无法执行。"""


def run_sqlite_integrity_check(conn, *, logger, check_label: str, execute_failed_hint: str) -> None:
    """在同一连接校验 SQLite 完整性与业务表；失败抛出 BackupIntegrityError。"""
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
        has_user_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name <> 'SchemaVersion' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
    except Exception as e:
        fallback_log(logger, "error", f"{check_label}执行失败：{e}")
        raise BackupIntegrityError(f"{check_label}执行失败（{execute_failed_hint}）：{e}") from e
    msg0 = str(rows[0][0] if rows else "").strip().lower()
    if msg0 != "ok":
        fallback_log(logger, "error", f"{check_label}未通过：{rows}")
        raise BackupIntegrityError(f"{check_label}失败：{rows}")
    if has_user_table is None:
        message = f"{check_label}失败：空数据库或缺少业务表"
        fallback_log(logger, "error", message)
        raise BackupIntegrityError(message)
