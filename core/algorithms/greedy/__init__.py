from __future__ import annotations

"""
贪心排产算法（Phase 7 / P7-02, P7-06）。

拆分结构：
- scheduler.py：主流程（GreedyScheduler）
- seed.py：seed_results 规范化与去重
- auto_assign.py：内部工序缺省资源时自动选人/选机
- external_groups.py：外协工序（含 merged 外部组）
- downtime.py：区间重叠/占用等工具函数
"""

from core.algorithms.types import ScheduleResult, ScheduleSummary

from .scheduler import GreedyScheduler

__all__ = [
    "GreedyScheduler",
    "ScheduleResult",
    "ScheduleSummary",
]

