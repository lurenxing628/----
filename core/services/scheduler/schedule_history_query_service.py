from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models import ScheduleHistory
from data.repositories import ScheduleHistoryRepository


class ScheduleHistoryQueryService:
    """排产历史查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = ScheduleHistoryRepository(conn, logger=logger)

    def list_recent(self, limit: int = 20) -> List[ScheduleHistory]:
        return self.repo.list_recent(limit=int(limit))

    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.repo.list_versions(limit=int(limit))

    def get_by_version(self, version: int) -> Optional[ScheduleHistory]:
        return self.repo.get_by_version(int(version))

    def get_latest_version(self) -> int:
        return int(self.repo.get_latest_version() or 0)

