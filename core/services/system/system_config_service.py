from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors import AppError, ErrorCode
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


def _corrupt(key: str) -> AppError:
    return AppError(ErrorCode.DB_QUERY_ERROR, "系统配置里保存了无法识别的值，配置已损坏，请联系维护人员核对数据库。",
                    details={"config_key": key})


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
        # 这些值只由维护设置保存，写入口只写 yes/no 和范围内的整数；没保存过的键才用默认值，其他值都是存储损坏。
        def _get_yes_no(key: str, default: str) -> str:
            raw = stored_values.get(key)
            if raw is None:
                return default
            if raw not in ("yes", "no"):
                raise _corrupt(key)
            return raw

        def _get_int(key: str, default: int, min_v: int, max_v: int) -> int:
            raw = stored_values.get(key)
            if raw is None:
                return int(default)
            if re.fullmatch(r"[1-9][0-9]*", raw) is None or not min_v <= int(raw) <= max_v:
                raise _corrupt(key)
            return int(raw)

        return SystemConfigSnapshot(
            auto_backup_enabled=_get_yes_no("auto_backup_enabled", default="no"),
            auto_backup_interval_minutes=_get_int(
                "auto_backup_interval_minutes", default=60, min_v=self.MIN_INTERVAL_MINUTES, max_v=self.MAX_INTERVAL_MINUTES
            ),
            auto_backup_cleanup_enabled=_get_yes_no("auto_backup_cleanup_enabled", default="no"),
            auto_backup_keep_days=_get_int("auto_backup_keep_days", default=int(backup_keep_days_default), min_v=self.MIN_KEEP_DAYS, max_v=self.MAX_KEEP_DAYS),
            auto_backup_cleanup_interval_minutes=_get_int(
                "auto_backup_cleanup_interval_minutes", default=1440, min_v=self.MIN_INTERVAL_MINUTES, max_v=self.MAX_INTERVAL_MINUTES
            ),
            auto_log_cleanup_enabled=_get_yes_no("auto_log_cleanup_enabled", default="no"),
            auto_log_cleanup_keep_days=_get_int("auto_log_cleanup_keep_days", default=30, min_v=self.MIN_KEEP_DAYS, max_v=self.MAX_KEEP_DAYS),
            auto_log_cleanup_interval_minutes=_get_int(
                "auto_log_cleanup_interval_minutes", default=60, min_v=self.MIN_INTERVAL_MINUTES, max_v=self.MAX_INTERVAL_MINUTES
            ),
        )

    def snapshot_with_storage(self, backup_keep_days_default: int):
        stored = self.repo.read_values()
        return self._read_snapshot(backup_keep_days_default, stored), stored

    def get_snapshot_readonly(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        return self.snapshot_with_storage(backup_keep_days_default)[0]
