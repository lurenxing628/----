"""非 OR-Tools 排产搜索 profile 合同。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.errors import ValidationError

from .acceptance import ACCEPTANCE_IMPROVE_ONLY

PROFILE_BASELINE = "baseline"
PROFILE_VNS_SA = "vns_sa"
PROFILE_GRAPH_READY = "graph_ready"

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


def _profile_for_algo_mode(algo_mode: str) -> str:
    text = str(algo_mode or "").strip().lower()
    if text == "improve":
        return PROFILE_VNS_SA
    if text == "greedy":
        return PROFILE_BASELINE
    raise ValidationError(
        f"未知的计算模式“{algo_mode}”，无法确定搜索方案。",
        field="algo_mode",
    )


@dataclass(frozen=True)
class CandidateProfile:
    """单次 optimizer 运行的搜索 profile 合同。"""

    acceptance: str
    candidate_construction: Dict[str, Any]
    ortools_warmstart_enabled: bool


def build_candidate_profile(
    *,
    algo_mode: str,
    time_budget_seconds: int,
    ortools_enabled: bool,
    graph_sgs_required: bool,
) -> CandidateProfile:
    """解析并校验搜索 profile 合同。"""
    profile = _profile_for_algo_mode(algo_mode)
    if graph_sgs_required and profile == PROFILE_VNS_SA:
        profile = PROFILE_GRAPH_READY

    configured_budget = int(time_budget_seconds)
    if configured_budget < 1:
        raise ValidationError("时间预算必须为不小于 1 的整数。", field="time_budget_seconds")

    enabled = profile in (PROFILE_VNS_SA, PROFILE_GRAPH_READY)
    candidate_construction = (
        derive_grasp_ig_limits(configured_budget)
        if enabled and profile != PROFILE_GRAPH_READY
        else {}
    )
    return CandidateProfile(
        acceptance=ACCEPTANCE_IMPROVE_ONLY,
        candidate_construction=candidate_construction,
        ortools_warmstart_enabled=bool(ortools_enabled) and enabled,
    )


__all__ = [
    "CandidateProfile",
    "ITERATION_CEILING",
    "PROFILE_BASELINE",
    "PROFILE_GRAPH_READY",
    "PROFILE_VNS_SA",
    "RESTART_CEILING",
    "RESTART_FLOOR",
    "build_candidate_profile",
    "derive_grasp_ig_limits",
]
