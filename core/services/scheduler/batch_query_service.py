from __future__ import annotations

from data.repositories import BatchRepository


class BatchQueryService:
    """批次查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = BatchRepository(conn, logger=logger)

    def has_any(self) -> bool:
        return bool(self.repo.has_any())

