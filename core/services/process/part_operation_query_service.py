from __future__ import annotations

from typing import Any, Dict, List

from data.repositories import PartOperationRepository


class PartOperationQueryService:
    """零件工序查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = PartOperationRepository(conn, logger=logger)

    def list_all_active_with_details(self) -> List[Dict[str, Any]]:
        return self.repo.list_all_active_with_details()

    def list_active_hours(self) -> List[Dict[str, Any]]:
        return self.repo.list_active_hours()

    def list_internal_active_hours(self) -> List[Dict[str, Any]]:
        return self.repo.list_internal_active_hours()

