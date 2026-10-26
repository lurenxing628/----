from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.shared.boolean_normalize import normalize_yes_no_wide
from data.repositories import SystemConfigRepository


def _normalize_yes_no(value: Any) -> str:
    """
    统一把页面开关规范成系统内部保存值。
    """
    return normalize_yes_no_wide(value, default="no", unknown_policy="no")


def _switch_value_label(value: str) -> str:
    return "启用" if value == "yes" else "关闭"


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
    dirty_fields: List[str]
    dirty_reasons: Dict[str, str]


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
        dirty_fields: List[str] = []
        dirty_reasons: Dict[str, str] = {}

        def _mark_dirty(key: str, reason: str) -> None:
            dirty_fields.append(key)
            dirty_reasons[key] = reason

        def _get_yes_no(key: str, default: str) -> str:
            raw = stored_values.get(key, default)
            raw = default if raw is None else raw
            normalized = _normalize_yes_no(raw)
            raw_text = str(raw).strip()
            if raw_text and raw_text.lower() not in {"yes", "no"}:
                _mark_dirty(key, f"这个开关保存的是旧写法，本次先按“{_switch_value_label(normalized)}”处理。")
            elif not raw_text:
                _mark_dirty(key, f"这个开关保存为空，本次先按“{_switch_value_label(normalized)}”处理。")
            return normalized

        def _get_int(key: str, default: int, min_v: int, max_v: int) -> int:
            raw = stored_values.get(key)
            if raw is None:
                return int(default)
            raw_text = str(raw).strip()
            if raw_text == "":
                _mark_dirty(key, f"这个数字保存为空，本次先按 {default} 处理。")
                return int(default)
            try:
                v = int(raw_text)
            except ValueError:
                _mark_dirty(key, f"这个数字不是整数，本次先按 {default} 处理。")
                return int(default)
            if v < min_v:
                _mark_dirty(key, f"这个数字小于允许范围，本次先按最小值 {min_v} 处理。")
                return int(min_v)
            if v > max_v:
                _mark_dirty(key, f"这个数字大于允许范围，本次先按最大值 {max_v} 处理。")
                return int(max_v)
            return int(v)

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
            dirty_fields=dirty_fields,
            dirty_reasons=dirty_reasons,
        )

    def snapshot_with_storage(self, backup_keep_days_default: int):
        stored = self.repo.read_values()
        return self._read_snapshot(backup_keep_days_default, stored), stored

    def get_snapshot_readonly(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        return self.snapshot_with_storage(backup_keep_days_default)[0]
