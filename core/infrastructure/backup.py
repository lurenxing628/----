import os
import sqlite3
from datetime import datetime, timedelta
import logging


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

        source = sqlite3.connect(self.db_path)
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
            self.logger.info(f"数据库已备份：{backup_path}")
            return backup_path
        finally:
            source.close()
            dest.close()

    def restore(self, backup_path: str) -> bool:
        if not os.path.exists(backup_path):
            self.logger.error(f"备份文件不存在：{backup_path}")
            return False

        try:
            # 恢复前自动备份
            self.backup(suffix="before_restore")

            source = sqlite3.connect(backup_path)
            dest = sqlite3.connect(self.db_path)
            try:
                source.backup(dest)
            finally:
                source.close()
                dest.close()

            self.logger.info(f"数据库已恢复：{backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"数据库恢复失败：{e}")
            return False

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

