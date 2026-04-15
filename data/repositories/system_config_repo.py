from __future__ import annotations

from typing import List, Optional, Tuple

from core.models import SystemConfig

from .base_repo import BaseRepository


class SystemConfigRepository(BaseRepository):
    """系统配置仓库（SystemConfig）。用于系统管理：自动备份/自动清理等设置项。"""

    def get(self, config_key: str) -> Optional[SystemConfig]:
        row = self.fetchone(
            "SELECT id, config_key, config_value, description, updated_at FROM SystemConfig WHERE config_key = ?",
            (str(config_key),),
        )
        return SystemConfig.from_row(row) if row else None

    def get_value(self, config_key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.fetchvalue(
            "SELECT config_value FROM SystemConfig WHERE config_key = ?",
            (str(config_key),),
            default=default,
        )
        return str(val) if val is not None else default

    def get_value_with_presence(self, config_key: str) -> Tuple[bool, Optional[str]]:
        row = self.fetchone(
            "SELECT config_value FROM SystemConfig WHERE config_key = ?",
            (str(config_key),),
        )
        if row is None:
            return False, None
        raw = row.get("config_value")
        return True, (None if raw is None else str(raw))

    def list_all(self) -> List[SystemConfig]:
        rows = self.fetchall("SELECT id, config_key, config_value, description, updated_at FROM SystemConfig ORDER BY config_key")
        return [SystemConfig.from_row(r) for r in rows]

    def set(self, config_key: str, config_value: str, description: Optional[str] = None) -> None:
        self.execute(
            """
            INSERT INTO SystemConfig (config_key, config_value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(config_key) DO UPDATE SET
              config_value = excluded.config_value,
              description = COALESCE(excluded.description, SystemConfig.description),
              updated_at = CURRENT_TIMESTAMP
            """,
            (str(config_key), str(config_value), description),
        )

    def delete(self, config_key: str) -> None:
        self.execute("DELETE FROM SystemConfig WHERE config_key = ?", (str(config_key),))

