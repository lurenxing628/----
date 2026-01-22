from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ValidationResult(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    WARNING = "warning"


@dataclass
class Operation:
    seq: int
    source: str  # internal/external
    status: str = "active"


@dataclass
class DeletionCheckResult:
    """删除检查结果（message 必须中文）。"""

    result: ValidationResult
    can_delete: bool
    message: str
    affected_ops: Optional[List[int]] = None  # 受影响工序（用于提示用户）


class DeletionValidator:
    """
    外部工序删除验证器（按开发文档 8.x 规则保留）。

    规则总结：
    - 首部连续外部工序：可删
    - 尾部连续外部工序：可删
    - 中间外部工序（含中间连续外部组）：不可删
    """

    def can_delete(self, operations: List[Operation], to_delete: List[int]) -> DeletionCheckResult:
        to_delete_set = set([int(x) for x in (to_delete or [])])

        # 过滤掉已删除的工序
        active_ops = [op for op in (operations or []) if op.status == "active"]

        # 检查：要删除的必须都是外部工序
        for seq in to_delete_set:
            op = self._find_op(active_ops, seq)
            if op is None:
                return DeletionCheckResult(
                    result=ValidationResult.DENIED,
                    can_delete=False,
                    message=f"工序 {seq} 不存在或已删除",
                )
            if op.source == "internal":
                return DeletionCheckResult(
                    result=ValidationResult.DENIED,
                    can_delete=False,
                    message=f"工序 {seq} 是内部工序，不能删除。只能删除外部工序。",
                )

        # 构建删除后的工序列表
        remaining = [op for op in active_ops if op.seq not in to_delete_set]

        # 如果删除后没有工序了
        if not remaining:
            return DeletionCheckResult(
                result=ValidationResult.WARNING,
                can_delete=True,
                message="删除后将没有任何工序，确定继续？",
            )

        # 如果没有剩余内部工序，允许删除（但给出提醒）
        internal_ops = [op for op in remaining if op.source == "internal"]
        if len(internal_ops) == 0:
            return DeletionCheckResult(
                result=ValidationResult.WARNING,
                can_delete=True,
                message="删除后将没有内部工序，确定继续？",
            )

        if len(internal_ops) == 1:
            return DeletionCheckResult(
                result=ValidationResult.ALLOWED,
                can_delete=True,
                message="可以删除",
            )

        # 检查内部工序之间是否有外部工序断档
        internal_ops.sort(key=lambda x: x.seq)

        for i in range(len(internal_ops) - 1):
            current = internal_ops[i]
            next_op = internal_ops[i + 1]

            between_ops = [
                op for op in remaining if current.seq < op.seq < next_op.seq and op.source == "external"
            ]
            if between_ops:
                between_seqs = [op.seq for op in between_ops]
                return DeletionCheckResult(
                    result=ValidationResult.DENIED,
                    can_delete=False,
                    message=(
                        f"无法删除：工序 {current.seq} 和 {next_op.seq} 之间存在未删除的外部工序 {between_seqs}，"
                        f"删除后会导致工艺断档。如需删除，请一并删除这些工序。"
                    ),
                    affected_ops=between_seqs,
                )

        return DeletionCheckResult(result=ValidationResult.ALLOWED, can_delete=True, message="可以删除")

    def _find_op(self, operations: List[Operation], seq: int) -> Optional[Operation]:
        for op in operations or []:
            if int(op.seq) == int(seq):
                return op
        return None

    def get_deletable_external_ops(self, operations: List[Operation]) -> List[int]:
        """获取所有可删除的外部工序（逐个尝试判定）。"""
        active_ops = [op for op in (operations or []) if op.status == "active"]
        external_ops = [op for op in active_ops if op.source == "external"]
        deletable: List[int] = []
        for op in external_ops:
            result = self.can_delete(operations, [op.seq])
            if result.can_delete:
                deletable.append(op.seq)
        return deletable

    def get_deletion_groups(self, operations: List[Operation]) -> List[List[int]]:
        """
        获取可删除的外部工序组（首部连续外部组、尾部连续外部组）。
        """
        active_ops = sorted([op for op in (operations or []) if op.status == "active"], key=lambda x: x.seq)
        if not active_ops:
            return []

        groups: List[List[int]] = []

        # 首部连续外部组
        head_group: List[int] = []
        for op in active_ops:
            if op.source == "external":
                head_group.append(op.seq)
            else:
                break
        if head_group:
            groups.append(head_group)

        # 尾部连续外部组
        tail_group: List[int] = []
        for op in reversed(active_ops):
            if op.source == "external":
                tail_group.insert(0, op.seq)
            else:
                break
        if tail_group and tail_group != head_group:
            groups.append(tail_group)

        return groups

