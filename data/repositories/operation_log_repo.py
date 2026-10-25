from __future__ import annotations

from typing import List

from core.models.operation_log import OperationLog

from .base_repo import BaseRepository


class OperationLogRepository(BaseRepository):
    """操作日志仓库（OperationLogs）。主要用于查询（写入通常走 OperationLogger）。"""

    def list_recent(self, limit: int) -> List[OperationLog]:
        rows = self.fetchall(
            "SELECT id, log_time, log_level, module, action, target_type, target_id, operator, detail, error_code, error_message FROM OperationLogs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [OperationLog.from_row(r) for r in rows]

    def count_all(self) -> int:
        return int(self.fetchvalue("SELECT COUNT(*) FROM OperationLogs"))

    def count_before(self, cutoff: str) -> int:
        return int(self.fetchvalue("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", (cutoff,)))

    def delete_oldest_before(self, cutoff: str, limit: int) -> None:
        """删除 log_time 早于 cutoff 的最旧 limit 条（按 log_time、id 升序）。"""
        self.execute(
            """
            DELETE FROM OperationLogs
            WHERE id IN (
                SELECT id FROM OperationLogs
                WHERE log_time < ?
                ORDER BY log_time ASC, id ASC
                LIMIT ?
            )
            """,
            (cutoff, limit),
        )


