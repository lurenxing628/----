"""非 OR-Tools 排产搜索 profile 合同。"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class CandidateProfile:
    """单次 optimizer 运行的搜索 profile 合同。"""

    candidate_construction: Dict[str, Any]
    ortools_warmstart_enabled: bool


def build_candidate_profile(
    *,
    algo_mode: str,
    time_budget_seconds: int,
    ortools_enabled: bool,
    graph_sgs_required: bool,
) -> CandidateProfile:
    """解析搜索 profile 合同。"""
    enabled = algo_mode == "improve"
    candidate_construction = (
        derive_grasp_ig_limits(time_budget_seconds)
        if enabled and not graph_sgs_required
        else {}
    )
    return CandidateProfile(
        candidate_construction=candidate_construction,
        ortools_warmstart_enabled=bool(ortools_enabled) and enabled,
    )


__all__ = [
    "CandidateProfile",
    "ITERATION_CEILING",
    "RESTART_CEILING",
    "RESTART_FLOOR",
    "build_candidate_profile",
    "derive_grasp_ig_limits",
]
