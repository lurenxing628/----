from __future__ import annotations

"""
贪心排产算法（Phase 7 / P7-02, P7-06）。

拆分结构：
- scheduler.py：对外 façade（GreedyScheduler），负责参数/状态初始化与调度编排
- dispatch/：派工主循环（batch_order / sgs）
- seed.py：seed_results 规范化与去重
- auto_assign.py：内部工序缺省资源时自动选人/选机
- external_groups.py：外协工序（含 merged 外部组）
- downtime.py：资源时间线/区间重叠等工具函数
"""

from core.algorithms.types import ScheduleResult, ScheduleSummary

from .scheduler import GreedyScheduler

__all__ = [
    "GreedyScheduler",
    "ScheduleResult",
    "ScheduleSummary",
]

