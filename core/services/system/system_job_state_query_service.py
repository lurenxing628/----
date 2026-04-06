from __future__ import annotations

from typing import Optional

from core.models import SystemJobState
from data.repositories import SystemJobStateRepository


class SystemJobStateQueryService:
    """系统任务状态查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = SystemJobStateRepository(conn, logger=logger)

    def get(self, job_key: str) -> Optional[SystemJobState]:
        key = (str(job_key) if job_key is not None else "").strip()
        if not key:
            return None
        return self.repo.get(key)

