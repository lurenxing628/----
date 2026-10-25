"""Shared SQLite integrity checks for backup creation and restoration."""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .migration_common import fallback_log
from .safe_files import write_fixed_bytes


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
    msg0 = str((rows[0][0] if rows else "") or "").strip().lower()
    if msg0 != "ok":
        fallback_log(logger, "error", f"{check_label}未通过：{rows}")
        raise BackupIntegrityError(f"{check_label}失败：{rows}")
    if has_user_table is None:
        message = f"{check_label}失败：空数据库或缺少业务表"
        fallback_log(logger, "error", message)
        raise BackupIntegrityError(message)


@contextmanager
def validated_sqlite_backup_stage(payload: bytes, *, logger=None, directory: Optional[str] = None) -> Iterator[Path]:
    """Yield the validated isolated file, closed and ready for same-filesystem replacement."""
    check_label = "迁移回滚备份完整性检查"
    # Empty files are valid to SQLite; require a complete header and whole pages.
    page_size = int.from_bytes(payload[16:18], "big")
    if page_size == 1:
        page_size = 65536
    if (
        len(payload) < 100
        or payload[:16] != b"SQLite format 3\x00"
        or not 512 <= page_size <= 65536
        or page_size & (page_size - 1)
        or len(payload) % page_size
    ):
        message = f"{check_label}失败：文件头无效或页面被截断，拒绝恢复。"
        fallback_log(logger, "error", message)
        raise BackupIntegrityError(message)

    # Isolate even WAL-mode payloads from the source/target sidecars. Close the
    # staging file before sqlite3 opens it, and the connection before cleanup.
    with tempfile.TemporaryDirectory(prefix="aps-rollback-integrity-", dir=directory) as staging_directory:
        staged_path = Path(staging_directory) / "payload.db"
        write_fixed_bytes(staged_path, payload)
        try:
            with closing(sqlite3.connect(staged_path.as_uri() + "?mode=ro", uri=True)) as conn:
                run_sqlite_integrity_check(
                    conn,
                    logger=logger,
                    check_label=check_label,
                    execute_failed_hint="视为不可信备份，拒绝恢复",
                )
        except sqlite3.Error as exc:
            fallback_log(logger, "error", f"{check_label}执行失败：{exc}")
            raise BackupIntegrityError(f"{check_label}执行失败，拒绝恢复：{exc}") from exc
        yield staged_path
