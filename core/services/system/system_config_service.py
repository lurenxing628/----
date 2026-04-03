from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.enum_normalizers import normalize_yes_no_wide
from data.repositories import SystemConfigRepository


def _normalize_yes_no(value: Any) -> str:
    """
    统一把输入规范到 yes/no：
    - HTML checkbox：on/None
    - 常见布尔：true/false/1/0
    """
    return normalize_yes_no_wide(value, default="no", unknown_policy="no")


def _parse_int(value: Any, field: str, min_v: int, max_v: int) -> int:
    raw = "" if value is None else str(value).strip()
    if raw == "":
        raise ValidationError(f"“{field}”不能为空", field=field)
    try:
        v = int(raw)
    except Exception as e:
        raise ValidationError(f"“{field}”必须是整数", field=field) from e
    if v < min_v or v > max_v:
        raise ValidationError(f"“{field}”范围不合法（允许 {min_v}~{max_v}）", field=field)
    return v


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
    dirty_fields: list[str]
    dirty_reasons: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_backup_enabled": self.auto_backup_enabled,
            "auto_backup_interval_minutes": int(self.auto_backup_interval_minutes),
            "auto_backup_cleanup_enabled": self.auto_backup_cleanup_enabled,
            "auto_backup_keep_days": int(self.auto_backup_keep_days),
            "auto_backup_cleanup_interval_minutes": int(self.auto_backup_cleanup_interval_minutes),
            "auto_log_cleanup_enabled": self.auto_log_cleanup_enabled,
            "auto_log_cleanup_keep_days": int(self.auto_log_cleanup_keep_days),
            "auto_log_cleanup_interval_minutes": int(self.auto_log_cleanup_interval_minutes),
            "dirty_fields": list(self.dirty_fields or []),
            "dirty_reasons": dict(self.dirty_reasons or {}),
        }


class SystemConfigService:
    """
    系统管理配置服务（SystemConfig）。

    说明：
    - 这里的配置用于 /system 页面（自动备份/自动清理等），不与 ScheduleConfig 混用。
    - 默认值以“保守”为原则：自动任务默认关闭（enabled=no）。
    """

    # 合理范围（避免过度占用性能）
    MIN_INTERVAL_MINUTES = 1
    MAX_INTERVAL_MINUTES = 1440
    MIN_KEEP_DAYS = 1
    MAX_KEEP_DAYS = 365

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.tx = TransactionManager(conn)
        self.repo = SystemConfigRepository(conn, logger=logger)

    def _read_snapshot(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        dirty_fields: list[str] = []
        dirty_reasons: Dict[str, str] = {}

        def _mark_dirty(key: str, reason: str) -> None:
            field = str(key or "").strip()
            text = str(reason or "").strip()
            if not field or not text:
                return
            if field not in dirty_fields:
                dirty_fields.append(field)
            dirty_reasons[field] = text

        def _get_yes_no(key: str, default: str) -> str:
            raw = self.repo.get_value(key, default=default)
            normalized = _normalize_yes_no(raw)
            raw_text = "" if raw is None else str(raw).strip()
            if raw_text and raw_text.lower() not in {"yes", "no"}:
                _mark_dirty(key, f"原始值 {raw_text!r} 已兼容归一为 {normalized}。")
            elif raw is not None and not raw_text:
                _mark_dirty(key, f"原始值为空，已按 {normalized} 兼容读取。")
            return normalized

        def _get_int(key: str, default: int, min_v: int, max_v: int) -> int:
            raw = self.repo.get_value(key, default=None)
            if raw is None:
                return int(default)
            raw_text = str(raw).strip()
            if raw_text == "":
                _mark_dirty(key, f"原始值为空，已回退为 {default}。")
                return int(default)
            try:
                v = int(raw_text)
            except Exception:
                _mark_dirty(key, f"原始值 {raw_text!r} 不是整数，已回退为 {default}。")
                return int(default)
            if v < min_v:
                _mark_dirty(key, f"原始值 {raw_text!r} 小于最小值 {min_v}，已钳制为 {min_v}。")
                return int(min_v)
            if v > max_v:
                _mark_dirty(key, f"原始值 {raw_text!r} 大于最大值 {max_v}，已钳制为 {max_v}。")
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
            dirty_fields=list(dirty_fields),
            dirty_reasons=dict(dirty_reasons),
        )

    def ensure_defaults(self, backup_keep_days_default: int) -> None:
        """
        确保必要的 key 已落库（缺失则写入，不覆盖用户已有配置）。
        """
        existing = {c.config_key for c in self.repo.list_all()}

        # 自动任务默认关闭；但保留策略给一个默认值（便于用户一键开启）
        defaults: Dict[str, Tuple[str, str]] = {
            "auto_backup_enabled": ("no", "自动备份（按请求触发；正常退出时也受此开关控制）是否启用：yes/no"),
            "auto_backup_interval_minutes": ("60", "自动备份（按请求触发）触发间隔（分钟）"),
            "auto_backup_cleanup_enabled": ("no", "自动清理备份（按请求触发）是否启用：yes/no"),
            "auto_backup_keep_days": (str(int(backup_keep_days_default)), "备份保留天数（自动清理策略）"),
            "auto_backup_cleanup_interval_minutes": ("1440", "自动清理备份触发间隔（分钟）"),
            "auto_log_cleanup_enabled": ("no", "自动清理操作日志（按请求触发）是否启用：yes/no"),
            "auto_log_cleanup_keep_days": ("30", "操作日志保留天数（自动清理策略）"),
            "auto_log_cleanup_interval_minutes": ("60", "自动清理操作日志触发间隔（分钟）"),
        }

        to_set = [(k, v, d) for k, (v, d) in defaults.items() if k not in existing]
        if not to_set:
            return
        with self.tx.transaction():
            for k, v, d in to_set:
                self.repo.set(k, v, description=d)

    def get_snapshot(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        self.ensure_defaults(backup_keep_days_default=backup_keep_days_default)
        return self._read_snapshot(backup_keep_days_default=backup_keep_days_default)

    def get_snapshot_readonly(self, backup_keep_days_default: int) -> SystemConfigSnapshot:
        return self._read_snapshot(backup_keep_days_default=backup_keep_days_default)

    def get_value(self, config_key: str, default: Optional[str] = None) -> Optional[str]:
        return self.repo.get_value(config_key, default=default)

    def set_value(self, config_key: str, value: Any, description: Optional[str] = None) -> None:
        key = (str(config_key) if config_key is not None else "").strip()
        if not key:
            raise ValidationError("config_key 不能为空", field="config_key")
        val = "" if value is None else str(value)
        with self.tx.transaction():
            self.repo.set(key, val, description=description)

    def update_backup_settings(
        self,
        auto_backup_enabled: Any,
        auto_backup_interval_minutes: Any,
        auto_backup_cleanup_enabled: Any,
        auto_backup_keep_days: Any,
        auto_backup_cleanup_interval_minutes: Any,
    ) -> None:
        enabled = _normalize_yes_no(auto_backup_enabled)
        cleanup_enabled = _normalize_yes_no(auto_backup_cleanup_enabled)
        interval = _parse_int(auto_backup_interval_minutes, field="自动备份间隔(分钟)", min_v=self.MIN_INTERVAL_MINUTES, max_v=self.MAX_INTERVAL_MINUTES)
        keep_days = _parse_int(auto_backup_keep_days, field="备份保留天数", min_v=self.MIN_KEEP_DAYS, max_v=self.MAX_KEEP_DAYS)
        cleanup_interval = _parse_int(
            auto_backup_cleanup_interval_minutes,
            field="备份自动清理间隔(分钟)",
            min_v=self.MIN_INTERVAL_MINUTES,
            max_v=self.MAX_INTERVAL_MINUTES,
        )
        with self.tx.transaction():
            self.repo.set("auto_backup_enabled", enabled, description="自动备份（按请求触发；正常退出时也受此开关控制）是否启用：yes/no")
            self.repo.set("auto_backup_interval_minutes", str(interval), description="自动备份（按请求触发）触发间隔（分钟）")
            self.repo.set("auto_backup_cleanup_enabled", cleanup_enabled, description="自动清理备份（按请求触发）是否启用：yes/no")
            self.repo.set("auto_backup_keep_days", str(keep_days), description="备份保留天数（自动清理策略）")
            self.repo.set("auto_backup_cleanup_interval_minutes", str(cleanup_interval), description="自动清理备份触发间隔（分钟）")

    def update_logs_settings(self, auto_log_cleanup_enabled: Any, auto_log_cleanup_keep_days: Any, auto_log_cleanup_interval_minutes: Any) -> None:
        enabled = _normalize_yes_no(auto_log_cleanup_enabled)
        keep_days = _parse_int(auto_log_cleanup_keep_days, field="操作日志保留天数", min_v=self.MIN_KEEP_DAYS, max_v=self.MAX_KEEP_DAYS)
        interval = _parse_int(
            auto_log_cleanup_interval_minutes,
            field="日志自动清理间隔(分钟)",
            min_v=self.MIN_INTERVAL_MINUTES,
            max_v=self.MAX_INTERVAL_MINUTES,
        )
        with self.tx.transaction():
            self.repo.set("auto_log_cleanup_enabled", enabled, description="自动清理操作日志（按请求触发）是否启用：yes/no")
            self.repo.set("auto_log_cleanup_keep_days", str(keep_days), description="操作日志保留天数（自动清理策略）")
            self.repo.set("auto_log_cleanup_interval_minutes", str(interval), description="自动清理操作日志触发间隔（分钟）")

