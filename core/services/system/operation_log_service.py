from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.infrastructure.transaction import TransactionManager
from core.models import OperationLog
from data.repositories import OperationLogRepository


class OperationLogService:
    """操作日志服务（OperationLogs）。封装查询与删除（含事务）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx = TransactionManager(conn)
        self.repo = OperationLogRepository(conn, logger=logger)

    def list_recent(
        self,
        *,
        limit: int = 20,
        module: Optional[str] = None,
        action: Optional[str] = None,
        log_level: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[OperationLog]:
        return self.repo.list_recent(
            limit=int(limit),
            module=module,
            action=action,
            log_level=log_level,
            start_time=start_time,
            end_time=end_time,
        )

    def delete_by_id(self, log_id: int) -> int:
        deleted = 0
        lid = int(log_id)
        with self.tx.transaction():
            deleted = int(self.repo.delete_by_id(lid) or 0)
            if deleted > 0 and self.op_logger is not None:
                self.op_logger.info(
                    module="system",
                    action="logs_delete",
                    target_type="operation_log",
                    target_id=str(lid),
                    detail={"mode": "manual", "deleted_ids": [int(lid)], "deleted_count": 1},
                )
        return int(deleted)

    def delete_by_ids(self, log_ids: List[int]) -> int:
        ids = [int(x) for x in (log_ids or []) if int(x) > 0]
        deleted = 0
        with self.tx.transaction():
            deleted = int(self.repo.delete_by_ids(ids) or 0)
            if self.op_logger is not None:
                self.op_logger.info(
                    module="system",
                    action="logs_delete",
                    target_type="operation_log",
                    target_id=None,
                    detail={"mode": "batch", "deleted_count": int(deleted), "deleted_ids_sample": ids[:30]},
                )
        return int(deleted)

