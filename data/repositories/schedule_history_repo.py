from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models import ScheduleHistory

from .base_repo import BaseRepository


class ScheduleHistoryRepository(BaseRepository):
    """排产历史仓库（ScheduleHistory）。"""

    def get(self, history_id: int) -> Optional[ScheduleHistory]:
        row = self.fetchone(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory WHERE id = ?",
            (int(history_id),),
        )
        return ScheduleHistory.from_row(row) if row else None

    def list_recent(self, limit: int = 20) -> List[ScheduleHistory]:
        rows = self.fetchall(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        return [ScheduleHistory.from_row(r) for r in rows]

    def get_by_version(self, version: int) -> Optional[ScheduleHistory]:
        row = self.fetchone(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory WHERE version = ? ORDER BY id DESC LIMIT 1",
            (int(version),),
        )
        return ScheduleHistory.from_row(row) if row else None

    def get_latest_version(self) -> int:
        val = self.fetchvalue("SELECT COALESCE(MAX(version), 0) FROM ScheduleHistory", default=0)
        try:
            return int(val)
        except Exception:
            return 0

    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        返回最近版本列表（去重），用于页面下拉选择。
        """
        # 注意：strategy/result_status 不能用 MAX(text)（会变成字典序），需要取“最新一条记录”的值。
        rows = self.fetchall(
            """
            SELECT h.version, h.schedule_time, h.strategy, h.result_status
            FROM ScheduleHistory h
            WHERE h.id = (
                SELECT h2.id
                FROM ScheduleHistory h2
                WHERE h2.version = h.version
                ORDER BY h2.schedule_time DESC, h2.id DESC
                LIMIT 1
            )
            ORDER BY h.version DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return rows

    def create(self, payload: Dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO ScheduleHistory
            (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(payload.get("version") or 1),
                payload.get("strategy"),
                payload.get("batch_count"),
                payload.get("op_count"),
                payload.get("result_status"),
                payload.get("result_summary"),
                payload.get("created_by"),
            ),
        )

