from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta

_MAINT_MUTEX = threading.Lock()


class BackupManager:
    """数据库备份管理器（退出自动备份 + 手动备份/恢复/清理）。"""

    def __init__(
        self,
        db_path: str,
        backup_dir: str = "backups",
        keep_days: int = 7,
        logger: logging.Logger = None,
    ):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.keep_days = keep_days
        self.logger = logger or logging.getLogger(__name__)

        os.makedirs(backup_dir, exist_ok=True)

    def backup(self, suffix: str = None) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        backup_name = f"aps_backup_{timestamp}{suffix_str}.db"
        backup_path = os.path.join(self.backup_dir, backup_name)
        tmp_path = backup_path + ".tmp"

        try:
            # 先写入临时文件，成功后原子替换，避免留下半成品备份文件
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

            # 两次 connect 任一失败都必须确保已打开的连接能关闭（避免句柄泄漏）
            with closing(sqlite3.connect(self.db_path)) as source:
                with closing(sqlite3.connect(tmp_path)) as dest:
                    source.backup(dest)

                    # 备份后完整性校验（建议启用；失败则不生成最终备份文件）
                    try:
                        rows = dest.execute("PRAGMA integrity_check").fetchall() or []
                    except Exception as e:
                        # 校验执行失败：不阻断备份，但记录 warning 便于排障
                        self.logger.warning(f"备份 integrity_check 执行失败（已忽略）：{e}")
                    else:
                        msg0 = str((rows[0][0] if rows else "") or "").strip().lower()
                        if msg0 != "ok":
                            self.logger.error(f"备份 integrity_check 未通过：{rows}")
                            raise RuntimeError(f"backup integrity_check failed: {rows}")
            os.replace(tmp_path, backup_path)
            self.logger.info(f"数据库已备份：{backup_path}")
            return backup_path
        finally:
            # 异常路径清理临时文件（最佳努力）
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def restore(self, backup_path: str) -> bool:
        if not os.path.exists(backup_path):
            self.logger.error(f"备份文件不存在：{backup_path}")
            return False

        # 进程内互斥：避免同一进程内并发 restore/backup_restore 请求互相打爆
        if not _MAINT_MUTEX.acquire(blocking=False):
            self.logger.error("数据库正在维护/恢复中，请稍后重试。")
            return False

        lock_path = os.path.abspath(self.db_path) + ".maintenance.lock"
        lock_fd = None
        before_restore_path = None
        try:
            # 跨进程软锁（最佳努力）：至少避免多实例同时 restore
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(lock_fd, f"pid={os.getpid()} ts={datetime.now().isoformat()}".encode())
                except Exception:
                    pass
            except FileExistsError:
                self.logger.error(f"检测到维护锁文件，可能已有恢复任务在进行：{lock_path}")
                return False
            except Exception as e:
                # 锁文件创建失败不一定致命：继续尝试，但给出风险提示
                self.logger.warning(f"维护锁文件创建失败（将继续尝试恢复，但可能被并发任务干扰）：{e}")

            # 恢复前自动备份
            before_restore_path = self.backup(suffix="before_restore")

            # 处理“其它连接/Windows 锁”的最小策略：busy_timeout + 重试
            retries = 6
            for i in range(retries):
                try:
                    with closing(sqlite3.connect(backup_path)) as source:
                        with closing(sqlite3.connect(self.db_path, timeout=30)) as dest:
                            try:
                                dest.execute("PRAGMA busy_timeout = 30000")
                            except Exception:
                                pass
                            source.backup(dest)
                    self.logger.info(f"数据库已恢复：{backup_path}")
                    return True
                except sqlite3.OperationalError as e:
                    msg = str(e).lower()
                    if ("locked" in msg or "busy" in msg) and i < retries - 1:
                        self.logger.warning(f"数据库被占用（可能有其它连接未释放），准备重试：{e}")
                        time.sleep(0.2 * (i + 1))
                        continue
                    raise

        except Exception:
            self.logger.exception("数据库恢复失败")
            # 若恢复过程导致主库处于不一致状态，尽最大努力回滚到恢复前备份
            try:
                if before_restore_path and os.path.exists(before_restore_path):
                    retries = 6
                    for i in range(retries):
                        try:
                            with closing(sqlite3.connect(before_restore_path)) as source2:
                                with closing(sqlite3.connect(self.db_path, timeout=30)) as dest2:
                                    try:
                                        dest2.execute("PRAGMA busy_timeout = 30000")
                                    except Exception:
                                        pass
                                    source2.backup(dest2)
                            self.logger.error(f"数据库恢复失败，已自动回滚到恢复前备份：{before_restore_path}")
                            break
                        except sqlite3.OperationalError as e2:
                            msg2 = str(e2).lower()
                            if ("locked" in msg2 or "busy" in msg2) and i < retries - 1:
                                self.logger.warning(f"自动回滚时数据库被占用，准备重试：{e2}")
                                time.sleep(0.2 * (i + 1))
                                continue
                            raise
            except Exception:
                self.logger.exception("数据库恢复失败且自动回滚失败")
            return False
        finally:
            # 释放锁文件
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                pass
            try:
                _MAINT_MUTEX.release()
            except Exception:
                pass

    def cleanup_old_backups(self):
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        if not os.path.exists(self.backup_dir):
            return

        for filename in os.listdir(self.backup_dir):
            if not filename.startswith("aps_backup_"):
                continue

            filepath = os.path.join(self.backup_dir, filename)
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)
                    self.logger.info(f"已清理过期备份：{filename}")
            except Exception as e:
                self.logger.warning(f"清理备份失败（{filename}）：{e}")

    def list_backups(self) -> list:
        backups = []
        if not os.path.exists(self.backup_dir):
            return backups

        for filename in sorted(os.listdir(self.backup_dir), reverse=True):
            if not filename.startswith("aps_backup_"):
                continue

            filepath = os.path.join(self.backup_dir, filename)
            stat = os.stat(filepath)
            backups.append(
                {
                    "filename": filename,
                    "path": filepath,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        return backups

