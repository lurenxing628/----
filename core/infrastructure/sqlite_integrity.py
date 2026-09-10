"""Shared SQLite integrity checks for backup creation and restoration."""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .migration_common import fallback_log
from .safe_files import write_fixed_bytes


class BackupIntegrityError(RuntimeError):
    """备份/恢复源文件未通过 PRAGMA integrity_check（或校验本身跑不起来）。"""


def run_sqlite_integrity_check(conn, *, logger, check_label: str, execute_failed_hint: str) -> None:
    """对连接执行 PRAGMA integrity_check；跑不起来或结果≠ok 一律 raise BackupIntegrityError。"""
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall() or []
    except Exception as e:
        fallback_log(logger, "error", f"{check_label}执行失败：{e}")
        raise BackupIntegrityError(f"{check_label}执行失败（{execute_failed_hint}）：{e}") from e
    msg0 = str((rows[0][0] if rows else "") or "").strip().lower()
    if msg0 != "ok":
        fallback_log(logger, "error", f"{check_label}未通过：{rows}")
        raise BackupIntegrityError(f"{check_label}失败：{rows}")


def validate_sqlite_backup_payload(payload: bytes, *, logger=None) -> None:
    """Validate only the captured bytes, without opening the source or target database."""
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
    with tempfile.TemporaryDirectory(prefix="aps-rollback-integrity-") as directory:
        staged_path = Path(directory) / "payload.db"
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
