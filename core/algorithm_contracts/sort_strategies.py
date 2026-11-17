"""
排序策略系统（Phase 7 / P7-01）。

文档参考：开发文档.md -> 10. 排产算法 -> 10.1/10.2
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, cast

from core.models.enums import SortStrategy

from .priority_constants import PRIORITY_RANK, PRIORITY_SCORE


@dataclass(frozen=True)
class WeightedParams:
    """The weighted strategy's two weights; every other strategy takes none."""

    priority_weight: float
    due_weight: float

    def public_dict(self) -> Dict[str, float]:
        return {"priority_weight": self.priority_weight, "due_weight": self.due_weight}


@dataclass
class BatchForSort:
    """用于排序的批次信息（从 Batch 标准化得到）。"""

    batch_id: str
    priority: str  # normal/urgent/critical
    due_date: Optional[date] = None
    created_at: Optional[datetime] = None


class BaseSortStrategy(ABC):
    """排序策略基类。"""

    @abstractmethod
    def sort(self, batches: Sequence[BatchForSort], *, base_date: date) -> List[BatchForSort]:
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError


class PriorityFirstStrategy(BaseSortStrategy):
    """优先级优先：critical > urgent > normal，同优先级按交期升序，同交期按批次号。"""

    def sort(self, batches: Sequence[BatchForSort], *, base_date: date) -> List[BatchForSort]:
        def sort_key(batch: BatchForSort):
            priority_rank = PRIORITY_RANK[batch.priority]
            due_rank = batch.due_date if batch.due_date else date.max
            return (priority_rank, due_rank, batch.batch_id)

        return sorted(batches, key=sort_key)

    def get_name(self) -> str:
        return "优先级优先"


class DueDateFirstStrategy(BaseSortStrategy):
    """交期优先：交期早的优先，无交期的排最后；同交期按优先级，同优先级按批次号。"""

    def sort(self, batches: Sequence[BatchForSort], *, base_date: date) -> List[BatchForSort]:
        def sort_key(batch: BatchForSort):
            has_due = 0 if batch.due_date else 1  # 无交期的排最后
            due_rank = batch.due_date if batch.due_date else date.max
            priority_rank = PRIORITY_RANK[batch.priority]
            return (has_due, due_rank, priority_rank, batch.batch_id)

        return sorted(batches, key=sort_key)

    def get_name(self) -> str:
        return "交期优先"


class WeightedStrategy(BaseSortStrategy):
    """
权重混合（加权评分后降序）：
score = priority_weight×priority_score + due_weight×due_score

说明：
- V1.1 起，“齐套权重”作为预留字段，不参与当前排序。
- 齐套状态是否作为排产门槛，由本次排产的 readiness_gate_enabled 控制。
"""

    def __init__(self, weights: WeightedParams):
        self.priority_weight = weights.priority_weight
        self.due_weight = weights.due_weight

    def sort(self, batches: Sequence[BatchForSort], *, base_date: date) -> List[BatchForSort]:
        def calc_score(batch: BatchForSort) -> float:
            priority_score = PRIORITY_SCORE[batch.priority]

            if batch.due_date:
                days_left = (batch.due_date - base_date).days
                due_score = 100 - min(max(days_left, 0), 100)
            else:
                due_score = 0

            return (self.priority_weight * priority_score) + (self.due_weight * due_score)

        # 分数降序，同分按批次号升序（稳定）
        return sorted(batches, key=lambda b: (-calc_score(b), b.batch_id))

    def get_name(self) -> str:
        return "权重混合"


class FIFOStrategy(BaseSortStrategy):
    """先进先出：按创建时间升序，同时间按批次号。"""

    def sort(self, batches: Sequence[BatchForSort], *, base_date: date) -> List[BatchForSort]:
        def sort_key(batch: BatchForSort):
            created = batch.created_at if batch.created_at else datetime.max
            return (created, batch.batch_id)

        return sorted(batches, key=sort_key)

    def get_name(self) -> str:
        return "先进先出"


class StrategyFactory:
    """策略工厂。"""

    _strategies = {
        SortStrategy.PRIORITY_FIRST: PriorityFirstStrategy,
        SortStrategy.DUE_DATE_FIRST: DueDateFirstStrategy,
        SortStrategy.WEIGHTED: WeightedStrategy,
        SortStrategy.FIFO: FIFOStrategy,
    }

    @classmethod
    def create(cls, strategy: SortStrategy, weights: Optional[WeightedParams]) -> BaseSortStrategy:
        """``weights`` is set exactly for the weighted strategy (resolve_optimizer_config pairs them)."""
        if strategy == SortStrategy.WEIGHTED:
            return WeightedStrategy(cast(WeightedParams, weights))
        return cls._strategies[strategy]()
