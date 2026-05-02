from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import PartOperationStatus, SourceType


class ValidationResult(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    WARNING = "warning"


@dataclass
class Operation:
    seq: int
    source: str  # 自制/外协
    status: str = PartOperationStatus.ACTIVE.value


@dataclass
class DeletionCheckResult:
    """删除检查结果（message 必须中文）。"""

    result: ValidationResult
    can_delete: bool
    message: str
    affected_ops: Optional[List[int]] = None  # 受影响工序（用于提示用户）


class DeletionValidator:
    """
    外协工序删除验证器（按开发文档 8.x 规则保留）。

    规则总结：
    - 首部连续外协工序：可删
    - 尾部连续外协工序：可删
    - 中间外协工序（含中间连续外协组）：不可删
    """

    @staticmethod
    def _norm_source(value: str) -> str:
        """
        将 source 规范化为系统内部使用的工序来源值。
        - 大小写/空格容错
        - 未知值保持为空，由上层拒绝删除，避免把异常来源误当成自制或外协工序
        """
        v = str(value or "").strip().lower()
        if v in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
            return v
        return ""

    @staticmethod
    def _norm_status(value: Any) -> str:
        """
        将 status 规范化为 active/deleted。
        - 大小写/空格容错
        - 未知值按 active 处理（更保守，避免误删）
        """
        v = str(value or "").strip().lower()
        return (
            PartOperationStatus.DELETED.value
            if v == PartOperationStatus.DELETED.value
            else PartOperationStatus.ACTIVE.value
        )

    def can_delete(self, operations: List[Operation], to_delete: List[int]) -> DeletionCheckResult:
        to_delete_set = set([int(x) for x in (to_delete or [])])
        active_ops = self._filter_active_ops(operations)
        op_map = self._build_op_map(active_ops)

        invalid_source = self._validate_sources(active_ops)
        if invalid_source is not None:
            return invalid_source

        invalid = self._validate_delete_targets(op_map, to_delete_set)
        if invalid is not None:
            return invalid

        remaining = [op for op in active_ops if int(op.seq) not in to_delete_set]
        early = self._check_remaining_sanity(remaining)
        if early is not None:
            return early

        internal_ops = [op for op in remaining if self._norm_source(op.source) == SourceType.INTERNAL.value]
        if len(internal_ops) == 0:
            return DeletionCheckResult(
                result=ValidationResult.WARNING,
                can_delete=True,
                message="删除后将没有自制工序，确定继续？",
            )
        if len(internal_ops) == 1:
            return DeletionCheckResult(result=ValidationResult.ALLOWED, can_delete=True, message="可以删除")

        internal_ops.sort(key=lambda x: int(x.seq))
        gap = self._find_external_gap(remaining, internal_ops)
        if gap is not None:
            left_seq, right_seq, between_seqs = gap
            return DeletionCheckResult(
                result=ValidationResult.DENIED,
                can_delete=False,
                message=(
                    f"无法删除：工序 {left_seq} 和 {right_seq} 之间还有未删除的外协工序 {between_seqs}，"
                    f"删除后会导致工艺断档。如需删除，请一并删除这些工序。"
                ),
                affected_ops=between_seqs,
            )

        return DeletionCheckResult(result=ValidationResult.ALLOWED, can_delete=True, message="可以删除")

    def _filter_active_ops(self, operations: List[Operation]) -> List[Operation]:
        return [
            op
            for op in (operations or [])
            if self._norm_status(getattr(op, "status", None)) == PartOperationStatus.ACTIVE.value
        ]

    @staticmethod
    def _build_op_map(active_ops: List[Operation]) -> Dict[int, Operation]:
        out: Dict[int, Operation] = {}
        for op in active_ops:
            try:
                out[int(op.seq)] = op
            except Exception:
                continue
        return out

    def _validate_delete_targets(
        self, op_map: Dict[int, Operation], to_delete_set: Set[int]
    ) -> Optional[DeletionCheckResult]:
        for seq in to_delete_set:
            op = op_map.get(int(seq))
            if op is None:
                return DeletionCheckResult(
                    result=ValidationResult.DENIED,
                    can_delete=False,
                    message=f"工序 {seq} 不存在或已删除",
                )
            if self._norm_source(op.source) == SourceType.INTERNAL.value:
                return DeletionCheckResult(
                    result=ValidationResult.DENIED,
                    can_delete=False,
                    message=f"工序 {seq} 是自制工序，不能删除。这里只能删除外协工序。",
                )
        return None

    def _validate_sources(self, active_ops: List[Operation]) -> Optional[DeletionCheckResult]:
        for op in active_ops:
            if self._norm_source(op.source):
                continue
            return DeletionCheckResult(
                result=ValidationResult.DENIED,
                can_delete=False,
                message=f"工序 {op.seq} 来源无效，不能判断是否可删除。",
                affected_ops=[int(op.seq)],
            )
        return None

    @staticmethod
    def _check_remaining_sanity(remaining: List[Operation]) -> Optional[DeletionCheckResult]:
        if not remaining:
            return DeletionCheckResult(
                result=ValidationResult.WARNING,
                can_delete=True,
                message="删除后将没有任何工序，确定继续？",
            )
        return None

    def _find_external_gap(
        self, remaining: List[Operation], internal_ops: List[Operation]
    ) -> Optional[Tuple[int, int, List[int]]]:
        for cur, nxt in zip(internal_ops, internal_ops[1:]):
            between_seqs = [
                int(op.seq)
                for op in remaining
                if int(cur.seq) < int(op.seq) < int(nxt.seq)
                and self._norm_source(op.source) == SourceType.EXTERNAL.value
            ]
            if between_seqs:
                return int(cur.seq), int(nxt.seq), between_seqs
        return None

    def get_deletion_groups(self, operations: List[Operation]) -> List[List[int]]:
        """
        获取可删除的外协工序组（首部连续外协组、尾部连续外协组）。
        """
        active_ops = sorted(
            [op for op in (operations or []) if self._norm_status(op.status) == PartOperationStatus.ACTIVE.value],
            key=lambda x: x.seq,
        )
        if not active_ops:
            return []
        if self._validate_sources(active_ops) is not None:
            return []

        groups: List[List[int]] = []

        # 首部连续外协组
        head_group: List[int] = []
        for op in active_ops:
            if self._norm_source(op.source) == SourceType.EXTERNAL.value:
                head_group.append(op.seq)
            else:
                break
        if head_group:
            groups.append(head_group)

        # 尾部连续外协组
        tail_group: List[int] = []
        for op in reversed(active_ops):
            if self._norm_source(op.source) == SourceType.EXTERNAL.value:
                tail_group.insert(0, op.seq)
            else:
                break
        if tail_group and tail_group != head_group:
            groups.append(tail_group)

        return groups
