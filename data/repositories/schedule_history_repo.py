from __future__ import annotations

from typing import Any, Dict, Optional, cast

from core.errors import AppError, ErrorCode
from core.models.schedule_history import ScheduleHistory

from .base_repo import BaseRepository, strict_non_negative_int


class ScheduleHistoryRepository(BaseRepository):
    """排产历史仓库（ScheduleHistory）。"""

    def get_by_version(self, version: int) -> Optional[ScheduleHistory]:
        row = self.fetchone(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory WHERE version = ? ORDER BY id DESC LIMIT 1",
            (version,),
        )
        return ScheduleHistory.from_row(row) if row else None

    def get_latest_version(self) -> int:
        try:
            val = self.fetchvalue("SELECT COALESCE(MAX(version), 0) FROM ScheduleHistory")
            latest = strict_non_negative_int(val, field="latest schedule version")
        except ValueError as exc:
            raise AppError(ErrorCode.DB_QUERY_ERROR, "读取最新排产版本失败，请查看日志。", cause=exc) from exc
        return latest

    def allocate_next_version(self) -> int:
        """
        原子分配排产版本号（避免并发下 MAX(version)+1 复用）。

        版本号只由这里从 `ScheduleVersionSeq` 自增表分配（version=PRIMARY KEY AUTOINCREMENT），
        所以 ScheduleHistory 的版本号不会超过序列表。允许“跳号”（例如落库失败/回滚），但保证不会复用。
        """
        cur = self.execute("INSERT INTO ScheduleVersionSeq DEFAULT VALUES")
        return cast(int, cur.lastrowid)

    def create(self, payload: Dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO ScheduleHistory
            (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["version"],
                payload["strategy"],
                payload["batch_count"],
                payload["op_count"],
                payload["result_status"],
                payload["result_summary"],
                payload["created_by"],
            ),
        )
