from __future__ import annotations

from typing import Any, Dict, List

from core.infrastructure.errors import BusinessError, ErrorCode

from .deletion_validator import DeletionValidator
from .deletion_validator import Operation as DeleteOp


class PartDeleteGuard:
    def __init__(
        self,
        *,
        op_repo: Any,
        group_repo: Any,
        tx_manager: Any,
        deletion_validator: DeletionValidator,
    ) -> None:
        self.op_repo = op_repo
        self.group_repo = group_repo
        self.tx_manager = tx_manager
        self.deletion_validator = deletion_validator

    def delete_external_group(self, *, part_no: str, group_id: str) -> Dict[str, Any]:
        group = self.group_repo.get(group_id)
        if not group or group.part_no != part_no:
            raise BusinessError(ErrorCode.EXTERNAL_GROUP_ERROR, "外协工序组不存在或不属于该零件")

        ops = self.op_repo.list_by_part(part_no, include_deleted=False)
        to_delete = self._active_external_group_seqs(ops, group_id)
        del_ops = self._to_delete_ops(ops)
        deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)
        if not any(sorted(group_seqs) == sorted(to_delete) for group_seqs in deletable_groups):
            raise BusinessError(
                ErrorCode.OPERATION_DELETE_DENIED,
                "不允许删除：只能删除开头或结尾连续的外协工序组，中间外协组不能单独删除。",
                details={"to_delete": to_delete, "deletable_groups": deletable_groups},
            )

        check = self.deletion_validator.can_delete(del_ops, to_delete=to_delete)
        if not check.can_delete:
            raise BusinessError(
                ErrorCode.OPERATION_DELETE_DENIED,
                check.message,
                details={"affected_ops": check.affected_ops},
            )

        with self.tx_manager.transaction():
            for seq in to_delete:
                self.op_repo.mark_deleted(part_no, seq)
            self.group_repo.delete(group_id)

        return {"message": check.message, "deleted_seqs": to_delete, "result": check.result.value}

    def calc_deletable_external_group_ids(self, part_no: str) -> List[str]:
        ops = self.op_repo.list_by_part(part_no, include_deleted=False)
        if not ops:
            return []

        del_ops = self._to_delete_ops(ops)
        deletable_groups = self.deletion_validator.get_deletion_groups(del_ops)
        deletable_seqs = {int(seq) for group in deletable_groups for seq in group}

        group_ids: List[str] = []
        for group in self.group_repo.list_by_part(part_no):
            seqs = self._active_external_group_seqs(ops, group.group_id)
            if seqs and all(seq in deletable_seqs for seq in seqs):
                group_ids.append(group.group_id)
        return group_ids

    @staticmethod
    def _active_external_group_seqs(ops: List[Any], group_id: str) -> List[int]:
        return [
            int(op.seq)
            for op in ops
            if op.ext_group_id == group_id and op.is_external() and op.is_active()
        ]

    @staticmethod
    def _to_delete_ops(ops: List[Any]) -> List[DeleteOp]:
        return [DeleteOp(seq=int(op.seq), source=op.source, status=op.status) for op in ops]
