from __future__ import annotations

from typing import Any, List, Optional

from core.models import OperationLog

from .base_repo import BaseRepository


class OperationLogRepository(BaseRepository):
    """操作日志仓库（OperationLogs）。主要用于查询（写入通常走 OperationLogger）。"""

    def list_recent(
        self,
        limit: int = 20,
        module: Optional[str] = None,
        action: Optional[str] = None,
        log_level: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[OperationLog]:
        sql = "SELECT id, log_time, log_level, module, action, target_type, target_id, operator, detail, error_code, error_message FROM OperationLogs"
        params: List[Any] = []
        where = []
        if module:
            where.append("module = ?")
            params.append(module)
        if action:
            where.append("action = ?")
            params.append(action)
        if log_level:
            where.append("log_level = ?")
            params.append(log_level)
        if start_time:
            where.append("log_time >= ?")
            params.append(start_time)
        if end_time:
            where.append("log_time <= ?")
            params.append(end_time)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        rows = self.fetchall(sql, tuple(params))
        return [OperationLog.from_row(r) for r in rows]

    def count_all(self) -> int:
        return int(self.fetchvalue("SELECT COUNT(*) FROM OperationLogs"))

    def count_before(self, cutoff: str) -> int:
        return int(self.fetchvalue("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", (cutoff,)))

    def delete_oldest_before(self, cutoff: str, limit: int) -> int:
        """删除 log_time 早于 cutoff 的最旧 limit 条（按 log_time、id 升序），返回影响行数。"""
        cur = self.execute(
            """
            DELETE FROM OperationLogs
            WHERE id IN (
                SELECT id FROM OperationLogs
                WHERE log_time < ?
                ORDER BY log_time ASC, id ASC
                LIMIT ?
            )
            """,
            (cutoff, int(limit)),
        )
        return int(cur.rowcount or 0)

    def delete_by_id(self, log_id: int) -> int:
        cur = self.execute("DELETE FROM OperationLogs WHERE id = ?", (int(log_id),))
        return int(cur.rowcount or 0)

    def delete_by_ids(self, log_ids: List[int]) -> int:
        ids = [int(x) for x in (log_ids or []) if str(x).strip() != ""]
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        cur = self.execute(f"DELETE FROM OperationLogs WHERE id IN ({placeholders})", tuple(ids))
        return int(cur.rowcount or 0)

