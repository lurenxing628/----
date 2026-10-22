from __future__ import annotations

from typing import Any

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OperatorMachine
from core.services.common.normalize import normalize_text
from data.repositories import MachineRepository, OperatorMachineRepository, OperatorRepository

from . import operator_machine_normalizers as om_normalizers
from .operator_machine_changes import prepare_operator_machine_changes


class OperatorMachineService:
    """人员-设备关联；所有入口先准备最终关系，再应用实际差异。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.tx_manager = TransactionManager(conn)
        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)
        self.repo = OperatorMachineRepository(conn, logger=logger)

    _normalize_skill_level_optional = staticmethod(om_normalizers.normalize_skill_level_optional)
    _normalize_yes_no_stored = staticmethod(om_normalizers.normalize_yes_no_stored)

    def _link_ids(self, operator_id, machine_id):
        op_id = normalize_text(operator_id)
        mc_id = normalize_text(machine_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        return op_id, mc_id

    @staticmethod
    def prepare_changes(current_rows, requested, *, removed=()):
        return prepare_operator_machine_changes(current_rows, requested, removed=removed)

    def apply_changes(self, changes):
        if not self.conn.in_transaction:
            raise RuntimeError("人员设备变更必须在写事务中应用。")
        for operator_id, machine_id in changes.removed:
            self.repo.remove(operator_id, machine_id)
        for link in changes.updated:
            self.repo.update_fields(link.operator_id, link.machine_id,
                                    skill_level=link.skill_level, is_primary=link.is_primary)
        return [self.repo.add(link.operator_id, link.machine_id,
                             skill_level=link.skill_level, is_primary=link.is_primary)
                for link in changes.added]

    def add_link(
        self,
        operator_id: Any,
        machine_id: Any,
        skill_level: str = "normal",
        is_primary: str = "no",
    ) -> OperatorMachine:
        op_id, mc_id = self._link_ids(operator_id, machine_id)
        with self.tx_manager.transaction():
            if not self.operator_repo.exists(op_id):
                raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{op_id}”不存在")
            if not self.machine_repo.exists(mc_id):
                raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{mc_id}”不存在")
            rows = self.repo.list_simple_rows_for_operators([op_id])
            if any(row["machine_id"] == mc_id for row in rows):
                raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "该人员与该设备已有关联，无需重复添加。")
            skill = self._normalize_skill_level_optional(skill_level) or "normal"
            primary = om_normalizers.normalize_yes_no_optional(is_primary, field="主操设备") or "no"
            changes = self.prepare_changes(rows, [OperatorMachine(None, op_id, mc_id, skill, primary)])
            return self.apply_changes(changes)[0]

    def remove_link(self, operator_id: Any, machine_id: Any) -> None:
        op_id, mc_id = self._link_ids(operator_id, machine_id)
        with self.tx_manager.transaction():
            rows = self.repo.list_simple_rows_for_operators([op_id])
            self.apply_changes(self.prepare_changes(rows, [], removed=[(op_id, mc_id)]))

    def update_link_fields(
        self,
        operator_id: Any,
        machine_id: Any,
        *,
        skill_level: Any,
        is_primary: Any,
    ) -> None:
        op_id, mc_id = self._link_ids(operator_id, machine_id)
        with self.tx_manager.transaction():
            rows = self.repo.list_simple_rows_for_operators([op_id])
            current = next((row for row in rows if row["machine_id"] == mc_id), None)
            if current is None:
                raise BusinessError(ErrorCode.NOT_FOUND, "未找到该人员与该设备的关联记录。")
            skill = self._normalize_skill_level_optional(skill_level) or "normal"
            primary = om_normalizers.normalize_yes_no_optional(is_primary, field="主操设备") or "no"
            changes = self.prepare_changes(rows, [OperatorMachine(None, op_id, mc_id, skill, primary)])
            self.apply_changes(changes)
