from __future__ import annotations

from typing import Any, Dict, List, Sequence

from data.repositories import OperatorMachineRepository


class OperatorMachineQueryService:
    """
    人员-设备关联查询服务（只读 façade）。

    目的：
    - 让 Route 层避免直接依赖 Repository
    - 不引入/改变写入语义（写入仍由 OperatorMachineService 负责）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = OperatorMachineRepository(conn, logger=logger)

    def list_simple_rows(self) -> List[Dict[str, Any]]:
        return self.repo.list_simple_rows()

    def list_with_names_by_machine(self) -> List[Dict[str, Any]]:
        return self.repo.list_with_names_by_machine()

    def list_with_names_by_operator(self) -> List[Dict[str, Any]]:
        return self.repo.list_with_names_by_operator()

    def list_links_with_operator_info(self) -> List[Dict[str, Any]]:
        return self.repo.list_links_with_operator_info()

    def list_simple_rows_for_machine_operator_sets(
        self,
        machine_ids: Sequence[str],
        operator_ids: Sequence[str],
    ) -> List[Dict[str, Any]]:
        return self.repo.list_simple_rows_for_machine_operator_sets(machine_ids, operator_ids)

