from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from core.models import ScheduleConfig

from .base_repo import BaseRepository


class ConfigRepository(BaseRepository):
    """排产配置仓库（ScheduleConfig）。"""

    def get(self, config_key: str) -> Optional[ScheduleConfig]:
        row = self.fetchone(
            "SELECT id, config_key, config_value, description, updated_at FROM ScheduleConfig WHERE config_key = ?",
            (config_key,),
        )
        return ScheduleConfig.from_row(row) if row else None

    def get_value(self, config_key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.fetchvalue(
            "SELECT config_value FROM ScheduleConfig WHERE config_key = ?",
            (config_key,),
            default=default,
        )
        return str(val) if val is not None else default

    def list_all(self) -> List[ScheduleConfig]:
        rows = self.fetchall(
            "SELECT id, config_key, config_value, description, updated_at FROM ScheduleConfig ORDER BY config_key"
        )
        return [ScheduleConfig.from_row(r) for r in rows]

    def set(self, config_key: str, config_value: str, description: Optional[str] = None) -> None:
        self.execute(
            """
            INSERT INTO ScheduleConfig (config_key, config_value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(config_key) DO UPDATE SET
              config_value = excluded.config_value,
              description = COALESCE(excluded.description, ScheduleConfig.description),
              updated_at = CURRENT_TIMESTAMP
            """,
            (config_key, str(config_value), description),
        )

    def set_batch(self, items: Iterable[Tuple[str, str, Optional[str]]]) -> None:
        rows = [(k, str(v), d) for k, v, d in items]
        if not rows:
            return
        self.executemany(
            """
            INSERT INTO ScheduleConfig (config_key, config_value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(config_key) DO UPDATE SET
              config_value = excluded.config_value,
              description = COALESCE(excluded.description, ScheduleConfig.description),
              updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )

    def delete(self, config_key: str) -> None:
        self.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (config_key,))

