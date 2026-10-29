from __future__ import annotations

from dataclasses import dataclass

from data.repositories import SystemConfigRepository


@dataclass
class SystemConfigSnapshot:
    auto_backup_enabled: str
    auto_backup_interval_minutes: int
    auto_backup_cleanup_enabled: str
    auto_backup_keep_days: int
    auto_backup_cleanup_interval_minutes: int
    auto_log_cleanup_enabled: str
    auto_log_cleanup_keep_days: int
    auto_log_cleanup_interval_minutes: int


class SystemConfigService:
    """
    系统管理配置服务（SystemConfig）。

    说明：
    - 这里的配置用于 /system 页面（自动备份/自动清理等），不与 ScheduleConfig 混用。
    - 默认值以“保守”为原则：自动任务默认关闭。
    """

    # 合理范围（避免过度占用性能）
    MIN_INTERVAL_MINUTES = 1
    MAX_INTERVAL_MINUTES = 1440
    MIN_KEEP_DAYS = 1
    MAX_KEEP_DAYS = 365

    def __init__(self, conn, logger=None):
        self.repo = SystemConfigRepository(conn, logger=logger)

    def _read_snapshot(self, backup_keep_days_default: int, stored_values) -> SystemConfigSnapshot:
        def _get_yes_no(key: str, default: str) -> str:
            raw = stored_values.get(key)
            return default if raw is None else str(raw)

        def _get_int(key: str, default: int) -> int:
            raw = stored_values.get(key)
            return int(default) if raw is None else int(raw)

        return SystemConfigSnapshot(
            auto_backup_enabled=_get_yes_no("auto_backup_enabled", default="no"),
            auto_backup_interval_minutes=_get_int("auto_backup_interval_minutes", default=60),
            auto_backup_cleanup_enabled=_get_yes_no("auto_backup_cleanup_enabled", default="no"),
            auto_backup_keep_days=_get_int("auto_backup_keep_days", default=int(backup_keep_days_default)),
            auto_backup_cleanup_interval_minutes=_get_int("auto_backup_cleanup_interval_minutes", default=1440),
            auto_log_cleanup_enabled=_get_yes_no("auto_log_cleanup_enabled", default="no"),
            auto_log_cleanup_keep_days=_get_int("auto_log_cleanup_keep_days", default=30),
            auto_log_cleanup_interval_minutes=_get_int("auto_log_cleanup_interval_minutes", default=60),
        )

    def snapshot_with_storage(self, backup_keep_days_default: int):
        stored = self.repo.read_values()
        return self._read_snapshot(backup_keep_days_default, stored), stored

    def get_snapshot_readonly(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        return self.snapshot_with_storage(backup_keep_days_default)[0]
