from __future__ import annotations

from typing import Set

from data.repositories import MachineDowntimeRepository


class MachineDowntimeQueryService:
    """设备停机查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = MachineDowntimeRepository(conn, logger=logger)

    def list_active_machine_ids_at(self, now_str: str) -> Set[str]:
        return self.repo.list_active_machine_ids_at(now_str)

