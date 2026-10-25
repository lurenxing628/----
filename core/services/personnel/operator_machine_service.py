from __future__ import annotations

from data.repositories import OperatorMachineRepository

from .operator_machine_changes import prepare_operator_machine_changes


class OperatorMachineService:
    """人员-设备关联；所有入口先准备最终关系，再应用实际差异。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = OperatorMachineRepository(conn, logger=logger)

    @staticmethod
    def prepare_changes(current_rows, requested, *, removed=(), primaries=None):
        return prepare_operator_machine_changes(current_rows, requested, removed=removed, primaries=primaries)

    def apply_changes(self, changes) -> None:
        if not self.conn.in_transaction:
            raise RuntimeError("人员设备变更必须在写事务中应用。")
        for operator_id, machine_id in changes.removed:
            self.repo.remove(operator_id, machine_id)
        for link in changes.updated:
            self.repo.update_fields(link.operator_id, link.machine_id,
                                    skill_level=link.skill_level, is_primary=link.is_primary)
        for link in changes.added:
            self.repo.add(link.operator_id, link.machine_id,
                          skill_level=link.skill_level, is_primary=link.is_primary)
