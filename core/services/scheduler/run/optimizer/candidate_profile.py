"""排产搜索的局部搜索与 GRASP / IG 候选构造预算。"""

from __future__ import annotations

from typing import Any, Dict

ITERATION_CEILING = 5000
RESTART_FLOOR = 50
RESTART_CEILING = 800

GRASP_RESTART_CEILING = 6
IG_RESTART_CEILING = 4
GRASP_RCL_SIZE_DEFAULT = 3
IG_DESTRUCTION_SIZE_DEFAULT = 3


def derive_grasp_ig_limits(time_budget_seconds: int) -> Dict[str, Any]:
    """把 optimizer 时间预算换算成 GRASP / IG 候选构造预算。"""
    budget = int(time_budget_seconds)
    configured_grasp_restarts = max(1, budget)
    configured_ig_restarts = max(1, int((budget + 1) / 2))
    return {
        "grasp": {
            "effective_restarts": min(configured_grasp_restarts, GRASP_RESTART_CEILING),
            "effective_rcl_size": GRASP_RCL_SIZE_DEFAULT,
        },
        "iterated_greedy": {
            "effective_restarts": min(configured_ig_restarts, IG_RESTART_CEILING),
            "effective_destruction_size": IG_DESTRUCTION_SIZE_DEFAULT,
        },
    }


__all__ = [
    "ITERATION_CEILING",
    "RESTART_CEILING",
    "RESTART_FLOOR",
    "derive_grasp_ig_limits",
]
