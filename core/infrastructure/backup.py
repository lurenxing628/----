"""数据库备份与恢复（BackupManager）。

维护窗互斥锁逻辑已按职责拆到 core/infrastructure/maintenance_lock.py（2026-07-19 B04 批次），
本模块保留调用方使用的维护窗公共 API。

备份完整性合同（B01/B05，2026-07-19 盲区扫描）：
- 备份创建后必须通过 PRAGMA integrity_check 才能升正式备份（既有 R32/O27 合同）；
- 恢复（含自动回滚）把任何源文件盖到主库前必须通过 PRAGMA integrity_check，
  失败抛 BackupIntegrityError，fail-loud 拒绝落地损坏库；
- 备份轮换由维护清理服务负责，数量保底共用 protected_recent_backup_paths。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
import traceback
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Set, Tuple
from urllib.parse import quote

from core.infrastructure.maintenance_lock import (
    MaintenanceWindowError,
    is_maintenance_window_active,
    maintenance_window,
)
from core.infrastructure.migration_common import fallback_log
from core.infrastructure.safe_files import (
    UnsafeFixedFileError,
    create_fixed_file_exclusive,
    guard_fixed_file_replace_target,
    remove_fixed_file,
    stat_regular_file,
)
from core.infrastructure.sqlite_integrity import BackupIntegrityError
from core.infrastructure.sqlite_integrity import run_sqlite_integrity_check as _run_sqlite_integrity_check

__all__ = [
    "BackupManager",
    "MIN_KEEP_BACKUPS",
    "MaintenanceWindowError",
    "RestoreResult",
    "is_maintenance_window_active",
    "maintenance_window",
    "protected_recent_backup_paths",
]

# 备份轮换修剪的数量保底：无论 keep_days 多短、停机多久，至少保留最新 N 份备份
#（对称于日志清理的 MIN_KEEP_LOGS 保底）。
MIN_KEEP_BACKUPS = 3


@dataclass(frozen=True)
class RestoreResult:
    ok: bool
    code: str
    message: str
    before_restore_path: Optional[str] = None


def _connect_existing_sqlite_file(path: str, **kwargs):
    path_abs = os.path.abspath(str(path))
    path_for_uri = path_abs.replace("\\", "/")
    uri = "file:" + quote(path_for_uri, safe="/:") + "?mode=rw"
    return sqlite3.connect(uri, uri=True, **kwargs)


def protected_recent_backup_paths(survey: Iterable[Tuple[datetime, str, str]], min_keep: int) -> Set[str]:
    """按 mtime 倒序取最新 min_keep 份的文件路径集合（备份修剪的数量保底，B01）。"""
    ordered = sorted(survey, key=lambda item: (item[0], item[1]), reverse=True)
    return {item[2] for item in ordered[: max(0, int(min_keep))]}


class BackupManager:
    def __init__(
        self,
        db_path: str,
        backup_dir: str = "backups",
        keep_days: int = 7,
        logger: Optional[logging.Logger] = None,
    ):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.keep_days = keep_days
        self.logger = logger or logging.getLogger(__name__)
        os.makedirs(backup_dir, exist_ok=True)

    def backup(self, suffix: Optional[str] = None) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        backup_name = f"aps_backup_{timestamp}{suffix_str}.db"
        backup_path = os.path.join(self.backup_dir, backup_name)
        tmp_path = backup_path + ".tmp"

        try:
            with maintenance_window(self.db_path, logger=self.logger, action="backup"):
                try:
                    remove_fixed_file(tmp_path)
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    raise RuntimeError(f"清理备份临时文件失败：{exc}") from exc

                try:
                    fd = create_fixed_file_exclusive(tmp_path)
                    os.close(fd)
                except Exception as exc:
                    raise RuntimeError(f"创建备份临时文件失败：{exc}") from exc

                stat_regular_file(self.db_path)
                with closing(_connect_existing_sqlite_file(self.db_path)) as source:
                    with closing(_connect_existing_sqlite_file(tmp_path)) as dest:
                        source.backup(dest)
                        _run_sqlite_integrity_check(
                            dest,
                            logger=self.logger,
                            check_label="备份后的数据库完整性检查",
                            execute_failed_hint="视为不可信备份，不落地",
                        )
                guard_fixed_file_replace_target(backup_path)
                os.replace(tmp_path, backup_path)
                fallback_log(self.logger, "info", f"数据库已备份：{backup_path}")
                return backup_path
        finally:
            try:
                remove_fixed_file(tmp_path)
            except FileNotFoundError:
                pass
            except Exception as exc:
                fallback_log(self.logger, "warning", f"清理备份临时文件失败（{tmp_path}）：{exc}")

    def _copy_db_file(self, source_path: str, *, locked_warning_message: str) -> None:
        retries = 6
        for i in range(retries):
            try:
                stat_regular_file(source_path)
                stat_regular_file(self.db_path)
                with closing(_connect_existing_sqlite_file(source_path)) as source:
                    # B05：任何源文件（用户选定的备份 / 自动回滚的 before_restore 快照）
                    # 盖到主库前先过 integrity_check；失败 fail-loud，绝不落地损坏库。
                    _run_sqlite_integrity_check(
                        source,
                        logger=self.logger,
                        check_label=f"恢复源文件完整性检查（{os.path.basename(source_path)}）",
                        execute_failed_hint="视为不可信备份，拒绝恢复",
                    )
                    with closing(_connect_existing_sqlite_file(self.db_path, timeout=30)) as dest:
                        dest.execute("PRAGMA busy_timeout = 30000")
                        source.backup(dest)
                return
            except (UnsafeFixedFileError, BackupIntegrityError):
                raise
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if ("locked" in message or "busy" in message) and i < retries - 1:
                    fallback_log(self.logger, "warning", f"{locked_warning_message}：{exc}")
                    time.sleep(0.2 * (i + 1))
                    continue
                raise

    def _auto_rollback(
        self,
        before_restore_path: Optional[str],
        *,
        failure_subject: str,
        rolled_back_code: str,
        rollback_failed_code: str,
    ) -> Optional[RestoreResult]:
        if not before_restore_path or not os.path.exists(before_restore_path):
            fallback_log(self.logger, "error", f"{failure_subject}，但缺少恢复前快照，无法自动回滚。")
            return None

        try:
            self._copy_db_file(before_restore_path, locked_warning_message="自动回滚时数据库被占用，准备重试")
        except Exception:
            fallback_log(self.logger, "error", f"{failure_subject}且自动回滚失败\n{traceback.format_exc()}")
            return RestoreResult(
                ok=False,
                code=rollback_failed_code,
                message=f"{failure_subject}，且自动回滚也失败了，请立即检查日志并手动校验数据库。",
                before_restore_path=before_restore_path,
            )

        snapshot_name = os.path.basename(before_restore_path)
        fallback_log(self.logger, "error", f"{failure_subject}，已自动回滚到恢复前备份：{before_restore_path}")
        return RestoreResult(
            ok=False,
            code=rolled_back_code,
            message=f"{failure_subject}，但已自动回滚到恢复前备份：{snapshot_name}。",
            before_restore_path=before_restore_path,
        )

    def restore(self, backup_path: str) -> RestoreResult:
        try:
            stat_regular_file(backup_path)
        except FileNotFoundError:
            fallback_log(self.logger, "error", f"备份文件不存在：{backup_path}")
            return RestoreResult(ok=False, code="backup_missing", message=f"备份文件不存在：{backup_path}")
        except OSError as e:
            fallback_log(self.logger, "error", f"备份文件不可读取：{backup_path}：{e}")
            return RestoreResult(ok=False, code="backup_unreadable", message=f"备份文件不可读取：{backup_path}")
        try:
            stat_regular_file(self.db_path)
        except (OSError, TypeError, ValueError) as e:
            fallback_log(self.logger, "error", f"数据库恢复目标不可写：{self.db_path}：{e}")
            return RestoreResult(ok=False, code="db_target_unreadable", message=f"数据库恢复目标不可写：{self.db_path}")

        before_restore_path = None
        try:
            with maintenance_window(self.db_path, logger=self.logger, action="restore"):
                try:
                    before_restore_path = self.backup(suffix="before_restore")
                except MaintenanceWindowError:
                    raise
                except Exception:
                    fallback_log(self.logger, "error", f"恢复前备份创建/完整性检查失败，已中止恢复（原库未改动）\n{traceback.format_exc()}")
                    return RestoreResult(
                        ok=False,
                        code="before_restore_backup_failed",
                        message="恢复前备份创建或完整性检查失败，数据库未恢复，原数据库没有被修改。请查看日志。",
                        before_restore_path=None,
                    )

                self._copy_db_file(backup_path, locked_warning_message="数据库被占用（可能有其它连接未释放），准备重试")
                fallback_log(self.logger, "info", f"数据库文件复制完成，等待后续结构校验：{backup_path}")
                return RestoreResult(
                    ok=True,
                    code="copied_pending_verify",
                    message=f"数据库文件已复制，等待后续结构校验：{backup_path}",
                    before_restore_path=before_restore_path,
                )
        except MaintenanceWindowError as e:
            fallback_log(self.logger, "warning" if e.code == "busy" else "error", e.message)
            return RestoreResult(ok=False, code=e.code, message=e.message)
        except BackupIntegrityError as e:
            # B05：备份文件未通过完整性检查——主库尚未被改动（校验在 source.backup(dest) 之前），
            # fail-loud 拒绝恢复并把可查原因给到用户，绝不落地损坏库。
            fallback_log(self.logger, "error", f"备份文件完整性检查未通过，已拒绝恢复（原数据库未修改）：{backup_path}：{e}")
            return RestoreResult(
                ok=False,
                code="backup_integrity_failed",
                message=f"备份文件完整性检查未通过，已拒绝恢复，原数据库未被修改：{os.path.basename(backup_path)}。请查看日志。",
                before_restore_path=before_restore_path,
            )
        except Exception:
            fallback_log(self.logger, "error", f"数据库恢复失败\n{traceback.format_exc()}")
            rollback_result = self._auto_rollback(
                before_restore_path,
                failure_subject="数据库恢复失败",
                rolled_back_code="restore_failed_rolled_back",
                rollback_failed_code="restore_failed_rollback_failed",
            )
            if rollback_result is not None:
                return rollback_result
            return RestoreResult(
                ok=False,
                code="restore_failed",
                message="数据库恢复失败，请查看日志。",
                before_restore_path=before_restore_path,
            )
