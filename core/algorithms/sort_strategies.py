from __future__ import annotations

"""
排序策略系统（Phase 7 / P7-01）。

文档参考：开发文档.md -> 10. 排产算法 -> 10.1/10.2
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .priority_constants import PRIORITY_ORDER, PRIORITY_SCORE, normalize_priority


class SortStrategy(Enum):
    PRIORITY_FIRST = "priority_first"
    DUE_DATE_FIRST = "due_date_first"
    WEIGHTED = "weighted"
    FIFO = "fifo"


@dataclass
class BatchForSort:
    """用于排序的批次信息（从 Batch 标准化得到）。"""

    batch_id: str
    priority: str  # normal/urgent/critical
    due_date: Optional[date] = None
    ready_status: str = "yes"  # yes/no/partial（当前排产仅允许 yes；此字段保留供未来扩展）
    ready_date: Optional[date] = None
    created_at: Optional[datetime] = None


class BaseSortStrategy(ABC):
    """排序策略基类。"""

    @abstractmethod
    def sort(self, batches: List[BatchForSort], *, base_date: Optional[date] = None) -> List[BatchForSort]:
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError


class PriorityFirstStrategy(BaseSortStrategy):
    """优先级优先：critical > urgent > normal，同优先级按交期升序，同交期按批次号。"""

    def sort(self, batches: List[BatchForSort], *, base_date: Optional[date] = None) -> List[BatchForSort]:
        def sort_key(batch: BatchForSort):
            pr = normalize_priority(batch.priority, default="normal")
            priority_rank = PRIORITY_ORDER.get(pr, 99)
            due_rank = batch.due_date if batch.due_date else date.max
            return (priority_rank, due_rank, batch.batch_id)

        return sorted(batches, key=sort_key)

    def get_name(self) -> str:
        return "优先级优先"


class DueDateFirstStrategy(BaseSortStrategy):
    """交期优先：交期早的优先，无交期的排最后；同交期按优先级，同优先级按批次号。"""

    def sort(self, batches: List[BatchForSort], *, base_date: Optional[date] = None) -> List[BatchForSort]:
        def sort_key(batch: BatchForSort):
            has_due = 0 if batch.due_date else 1  # 无交期的排最后
            due_rank = batch.due_date if batch.due_date else date.max
            pr = normalize_priority(batch.priority, default="normal")
            priority_rank = PRIORITY_ORDER.get(pr, 99)
            return (has_due, due_rank, priority_rank, batch.batch_id)

        return sorted(batches, key=sort_key)

    def get_name(self) -> str:
        return "交期优先"


class WeightedStrategy(BaseSortStrategy):
    """
权重混合（加权评分后降序）：
score = priority_weight×priority_score + due_weight×due_score

说明：
- V1.1 起，“齐套权重”作为预留字段，不参与当前排序（排产本身只排齐套批次）
"""

    def __init__(self, priority_weight: float = 0.4, due_weight: float = 0.5):
        self.priority_weight = float(priority_weight)
        self.due_weight = float(due_weight)

    def sort(self, batches: List[BatchForSort], *, base_date: Optional[date] = None) -> List[BatchForSort]:
        today = base_date or date.today()

        def calc_score(batch: BatchForSort) -> float:
            pr = normalize_priority(batch.priority, default="normal")
            priority_score = PRIORITY_SCORE.get(pr, 0)

            if batch.due_date:
                days_left = (batch.due_date - today).days
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

    def sort(self, batches: List[BatchForSort], *, base_date: Optional[date] = None) -> List[BatchForSort]:
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
    def create(cls, strategy: SortStrategy, **kwargs) -> BaseSortStrategy:
        strategy_class = cls._strategies.get(strategy)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {strategy}")

        if strategy == SortStrategy.WEIGHTED:
            # V1.1：忽略 ready_weight（预留字段，不参与当前排序）
            return strategy_class(
                priority_weight=kwargs.get("priority_weight", 0.4),
                due_weight=kwargs.get("due_weight", 0.5),
            )
        return strategy_class()

    @classmethod
    def get_available_strategies(cls) -> List[Dict[str, str]]:
        return [{"key": s.value, "name": cls.create(s).get_name()} for s in SortStrategy]


def parse_strategy(value: Any, default: SortStrategy = SortStrategy.PRIORITY_FIRST) -> SortStrategy:
    """
把字符串/枚举解析为 SortStrategy（容错：非法返回 default）。
"""
    if isinstance(value, SortStrategy):
        return value
    try:
        s = str(value or "").strip().lower()
        if not s:
            return default
        return SortStrategy(s)
    except Exception:
        return default

