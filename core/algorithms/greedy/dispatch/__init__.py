from __future__ import annotations

"""
派工（dispatch）子模块：

- batch_order：按批次顺序全局排序后逐条排入（保持 V1 行为）
- sgs：Serial SGS（eligible set）动态派工

说明：
- 该目录仅拆分“主循环/派工策略”，不改变 GreedyScheduler 对外 API。
"""

from .batch_order import dispatch_batch_order
from .sgs import dispatch_sgs

__all__ = [
    "dispatch_batch_order",
    "dispatch_sgs",
]

