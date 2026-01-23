from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models import OperationLog

from .base_repo import BaseRepository


class OperationLogRepository(BaseRepository):
    """操作日志仓库（OperationLogs）。主要用于查询（写入通常走 OperationLogger）。"""

    def get(self, log_id: int) -> Optional[OperationLog]:
        row = self.fetchone(
            "SELECT id, log_time, log_level, module, action, target_type, target_id, operator, detail, error_code, error_message FROM OperationLogs WHERE id = ?",
            (int(log_id),),
        )
        return OperationLog.from_row(row) if row else None

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

    def create(self, payload: Dict[str, Any]) -> None:
        """不建议业务直接使用：保留给测试/工具用途。"""
        self.execute(
            """
            INSERT INTO OperationLogs
            (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("log_level"),
                payload.get("module"),
                payload.get("action"),
                payload.get("target_type"),
                payload.get("target_id"),
                payload.get("operator"),
                payload.get("detail"),
                payload.get("error_code"),
                payload.get("error_message"),
            ),
        )

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

