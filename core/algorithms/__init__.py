"""
排产算法模块（可插拔）。

Phase 7（目标：M3）范围：
- 多策略排序（priority_first / due_date_first / weighted / fifo）
- 双资源约束贪心排产（设备 + 人员）+ 工作日历 + 外协周期（含外部组合并周期）

说明：
- V1 不引入并发/资源锁（仅做版本化落库与留痕）
- 用户可见信息尽量中文（错误提示/日志/报告）
"""

from .sort_strategies import SortStrategy, StrategyFactory, BatchForSort
from .types import ScheduleResult, ScheduleSummary
from .greedy import GreedyScheduler

__all__ = [
    "SortStrategy",
    "StrategyFactory",
    "BatchForSort",
    "GreedyScheduler",
    "ScheduleResult",
    "ScheduleSummary",
]

