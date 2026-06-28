"""非 OR-Tools 排产搜索 profile 合同（roadmap item 4）。

本模块只锁现有 optimizer 已有能力的 profile 合同与校验边界：

- 现有能力包括 ``baseline``（单次排产）与 ``grasp_ig``（多起点 + GRASP/IG 起点
  + 局部搜索，可选 OR-Tools warm-start）。
- 本阶段 ``repair`` 只允许 ``sgs``，``acceptance`` 只允许 ``improve_only``，
  ``neighborhoods`` 默认且仅允许业务邻域 registry 的六个邻域。
- ``configured`` 与 ``effective`` 必须区分：时间预算当前无系统上限，迭代上限受
  ``[200, 5000]`` 系统下/上限钳制，被钳制时如实写出 ``system_limit_applied`` 与
  ``system_limit_reason``。
- ``seed`` 由排产版本号派生，``seed_source`` 如实写出，不伪造成用户显式 seed。

本模块不实现 VNS / SA / ALNS，也不实现 CandidateFingerprint 的 hash 逻辑（属 item 5）。
public/diagnostics 分层投影由 summary 层
``optimizer_public_search_report`` 负责，本模块只产出结构化合同。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_neighborhood_moves import ALLOWED_NEIGHBORHOODS, BUSINESS_NEIGHBORHOODS

CANDIDATE_PROFILE_SCHEMA_VERSION = 1

PROFILE_BASELINE = "baseline"
PROFILE_MULTI_START_LOCAL_SEARCH = "multi_start_local_search"
PROFILE_GRASP_IG = "grasp_ig"
ALLOWED_PROFILES: Tuple[str, ...] = (PROFILE_BASELINE, PROFILE_MULTI_START_LOCAL_SEARCH, PROFILE_GRASP_IG)

# 本阶段只允许下列取值；扩展属后续 roadmap item，不在本轮范围。
ALLOWED_REPAIRS: Tuple[str, ...] = ("sgs",)
ALLOWED_ACCEPTANCES: Tuple[str, ...] = ("improve_only",)

# 迭代上限 / 重启阈值的系统钳制窗口（与历史 optimizer_local_search 内联公式逐位一致）。
ITERATION_FLOOR = 200
ITERATION_CEILING = 5000
RESTART_FLOOR = 50
RESTART_CEILING = 800
ITERATIONS_PER_SECOND = 20

GRASP_RESTART_CEILING = 6
IG_RESTART_CEILING = 4
GRASP_RCL_SIZE_DEFAULT = 3
IG_DESTRUCTION_SIZE_DEFAULT = 3

# system_limit_reason 取值（迭代上限来源）。
ITERATION_SOURCE_PROFILE_DEFAULT = "profile_default"
ITERATION_SOURCE_SYSTEM_LIMIT = "system_limit"
ITERATION_SOURCE_NOT_APPLICABLE = "not_applicable"
SYSTEM_LIMIT_REASON_FLOOR = "iteration_floor"
SYSTEM_LIMIT_REASON_CEILING = "iteration_ceiling"

SEED_SOURCE_OPTIMIZER_VERSION = "optimizer_version"

_PROFILE_FIELD_LABELS = {
    "profile": "搜索方案",
    "repair": "修复策略",
    "acceptance": "接受准则",
    "neighborhood": "邻域算子",
    "time_budget_seconds": "找更好排法先试多久",
    "seed": "随机种子",
}


def derive_iteration_limits(time_budget_seconds: int) -> Tuple[int, int]:
    """把时间预算换算成 ``(effective_max_iterations, restart_after)``。

    这是迭代上限/重启阈值钳制公式的**单一真相源**：optimizer 局部搜索与 profile
    合同都从这里取值，避免两处各算一遍导致语义漂移。公式与历史
    ``optimizer_local_search`` 内联实现逐位一致，纯集中、零行为变化。
    """
    budget = int(time_budget_seconds)
    it_limit = max(ITERATION_FLOOR, min(ITERATION_CEILING, budget * ITERATIONS_PER_SECOND))
    restart_after = max(RESTART_FLOOR, min(RESTART_CEILING, int(it_limit / 8) if it_limit > 0 else 200))
    return it_limit, restart_after


def derive_grasp_ig_limits(time_budget_seconds: int) -> Dict[str, Any]:
    """把 optimizer 时间预算换算成 GRASP / IG 候选构造预算。

    配置预算取自同一个 ``time_budget_seconds``，有效预算再按系统上限钳住，避免一次
    普通排产在大预算下突然解码过多候选。这里只计算预算，不做候选构造。
    """
    budget = int(time_budget_seconds)
    configured_grasp_restarts = max(1, budget)
    configured_ig_restarts = max(1, int((budget + 1) / 2))
    return {
        "schema_version": CANDIDATE_PROFILE_SCHEMA_VERSION,
        "seed_source": SEED_SOURCE_OPTIMIZER_VERSION,
        "grasp": {
            "configured_restarts": configured_grasp_restarts,
            "effective_restarts": min(configured_grasp_restarts, GRASP_RESTART_CEILING),
            "configured_rcl_size": GRASP_RCL_SIZE_DEFAULT,
            "effective_rcl_size": GRASP_RCL_SIZE_DEFAULT,
        },
        "iterated_greedy": {
            "configured_restarts": configured_ig_restarts,
            "effective_restarts": min(configured_ig_restarts, IG_RESTART_CEILING),
            "configured_destruction_size": IG_DESTRUCTION_SIZE_DEFAULT,
            "effective_destruction_size": IG_DESTRUCTION_SIZE_DEFAULT,
        },
    }


def _profile_label(field: str) -> str:
    return _PROFILE_FIELD_LABELS.get(str(field).strip(), str(field).strip() or "配置项")


def _require_allowed(value: Any, allowed: Tuple[str, ...], *, field: str) -> str:
    text = str(value or "").strip().lower()
    if text not in set(allowed):
        label = _profile_label(field)
        raise ValidationError(
            f"“{label}”当前不支持取值“{value}”，本阶段只允许：{', '.join(allowed)}。",
            field=field,
        )
    return text


def _require_neighborhoods(values: Tuple[str, ...]) -> Tuple[str, ...]:
    out = []
    for item in values:
        text = str(item or "").strip().lower()
        if text not in set(ALLOWED_NEIGHBORHOODS):
            label = _profile_label("neighborhood")
            raise ValidationError(
                f"“{label}”当前不支持“{item}”，本阶段只允许：{', '.join(ALLOWED_NEIGHBORHOODS)}。",
                field="neighborhood",
            )
        out.append(text)
    return tuple(out)


def _profile_for_algo_mode(algo_mode: str) -> str:
    text = str(algo_mode or "").strip().lower()
    if text == "improve":
        return PROFILE_GRASP_IG
    if text == "greedy":
        return PROFILE_BASELINE
    raise ValidationError(
        f"未知的计算模式“{algo_mode}”，无法确定搜索方案。",
        field="algo_mode",
    )


def _build_message(
    *,
    enabled: bool,
    configured_budget: int,
    configured_iters: int,
    effective_iters: int,
    system_limit_applied: bool,
    system_limit_reason: Optional[str],
) -> str:
    if not enabled:
        return "基础排产模式：仅单次排产，未启用多起点与局部搜索增强；随机种子由排产版本号自动派生（非手工指定）。"
    parts = [
        f"多起点+GRASP/IG候选+局部搜索模式：配置时间预算 {configured_budget} 秒，目标迭代上限 {configured_iters} 次。"
    ]
    if system_limit_applied and system_limit_reason == SYSTEM_LIMIT_REASON_FLOOR:
        parts.append(f"实际迭代上限被系统下限抬升到 {effective_iters} 次。")
    elif system_limit_applied:
        parts.append(f"实际迭代上限被系统上限压低到 {effective_iters} 次。")
    else:
        parts.append(f"实际迭代上限 {effective_iters} 次。")
    parts.append("随机种子由排产版本号自动派生（非手工指定）。")
    return "".join(parts)


@dataclass(frozen=True)
class CandidateProfile:
    """单次 optimizer 运行的搜索 profile 合同（结构化、可校验、可报告）。"""

    profile: str
    enabled: bool
    seed: int
    seed_source: str
    configured_time_budget_seconds: int
    effective_time_budget_seconds: int
    configured_max_iterations: int
    effective_max_iterations: int
    iteration_limit_source: str
    restart_after_iterations: int
    system_limit_applied: bool
    system_limit_reason: Optional[str]
    repair: str
    acceptance: str
    neighborhoods: Tuple[str, ...]
    candidate_strategy_family: str
    candidate_strategy_families: Tuple[str, ...]
    candidate_construction: Dict[str, Any]
    dispatch_mode: str
    dispatch_rule: str
    ortools_warmstart_enabled: bool
    strict_mode: bool
    validation_status: str
    message: str

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CANDIDATE_PROFILE_SCHEMA_VERSION,
            "profile": self.profile,
            "enabled": self.enabled,
            "seed": int(self.seed),
            "seed_source": self.seed_source,
            "configured_time_budget_seconds": int(self.configured_time_budget_seconds),
            "effective_time_budget_seconds": int(self.effective_time_budget_seconds),
            "configured_max_iterations": int(self.configured_max_iterations),
            "effective_max_iterations": int(self.effective_max_iterations),
            "iteration_limit_source": self.iteration_limit_source,
            "restart_after_iterations": int(self.restart_after_iterations),
            "system_limit_applied": bool(self.system_limit_applied),
            "system_limit_reason": self.system_limit_reason,
            "repair": self.repair,
            "acceptance": self.acceptance,
            "neighborhoods": list(self.neighborhoods),
            "candidate_strategy_family": self.candidate_strategy_family,
            "candidate_strategy_families": list(self.candidate_strategy_families),
            "candidate_construction": dict(self.candidate_construction or {}),
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "ortools_warmstart_enabled": bool(self.ortools_warmstart_enabled),
            "strict_mode": bool(self.strict_mode),
            "validation_status": self.validation_status,
            "message": self.message,
        }


def build_candidate_profile(
    *,
    algo_mode: str,
    dispatch_mode: str,
    dispatch_rule: str,
    time_budget_seconds: int,
    version: int,
    strict_mode: bool,
    ortools_enabled: bool,
    graph_sgs_required: bool,
    repair: str = "sgs",
    acceptance: str = "improve_only",
    neighborhoods: Optional[Tuple[str, ...]] = None,
) -> CandidateProfile:
    """解析并校验搜索 profile 合同。

    校验失败一律 fail-loud（与 strict_mode 无关）：profile 合同错误是合同违反，
    不是可选候选拒绝，不能静默回退默认值，也不能在非 strict 下被吞掉。

    ``neighborhoods`` 默认按 profile 派生（improve 用业务邻域 registry，baseline 为空）；
    若调用方显式传入，则逐项校验，未知邻域 fail-loud。
    """
    profile = _profile_for_algo_mode(algo_mode)
    repair_value = _require_allowed(repair, ALLOWED_REPAIRS, field="repair")
    acceptance_value = _require_allowed(acceptance, ALLOWED_ACCEPTANCES, field="acceptance")

    configured_budget = int(time_budget_seconds)
    if configured_budget < 1:
        raise ValidationError("时间预算必须为不小于 1 的整数。", field="time_budget_seconds")

    enabled = profile in (PROFILE_MULTI_START_LOCAL_SEARCH, PROFILE_GRASP_IG)
    effective_dispatch_mode = "sgs" if graph_sgs_required else str(dispatch_mode or "").strip().lower()
    resolved_neighborhoods = (BUSINESS_NEIGHBORHOODS if enabled else ()) if neighborhoods is None else tuple(neighborhoods)
    validated_neighborhoods = _require_neighborhoods(resolved_neighborhoods)
    ortools_warmstart_enabled = bool(ortools_enabled) and enabled

    if enabled:
        configured_iters = configured_budget * ITERATIONS_PER_SECOND
        effective_iters, restart_after = derive_iteration_limits(configured_budget)
        if effective_iters == configured_iters:
            system_limit_applied = False
            system_limit_reason: Optional[str] = None
            iteration_limit_source = ITERATION_SOURCE_PROFILE_DEFAULT
        else:
            system_limit_applied = True
            iteration_limit_source = ITERATION_SOURCE_SYSTEM_LIMIT
            system_limit_reason = (
                SYSTEM_LIMIT_REASON_FLOOR if effective_iters > configured_iters else SYSTEM_LIMIT_REASON_CEILING
            )
        effective_budget = configured_budget
        candidate_strategy_family = "multi_start_grasp_ig"
        candidate_strategy_families = ("multi_start", "grasp", "iterated_greedy")
        candidate_construction = derive_grasp_ig_limits(configured_budget)
    else:
        configured_iters = 0
        effective_iters = 0
        restart_after = 0
        system_limit_applied = False
        system_limit_reason = None
        iteration_limit_source = ITERATION_SOURCE_NOT_APPLICABLE
        effective_budget = 0
        candidate_strategy_family = "single_shot"
        candidate_strategy_families = ("single_shot",)
        candidate_construction = {}

    message = _build_message(
        enabled=enabled,
        configured_budget=configured_budget,
        configured_iters=configured_iters,
        effective_iters=effective_iters,
        system_limit_applied=system_limit_applied,
        system_limit_reason=system_limit_reason,
    )

    return CandidateProfile(
        profile=profile,
        enabled=enabled,
        seed=int(version),
        seed_source=SEED_SOURCE_OPTIMIZER_VERSION,
        configured_time_budget_seconds=configured_budget,
        effective_time_budget_seconds=effective_budget,
        configured_max_iterations=configured_iters,
        effective_max_iterations=effective_iters,
        iteration_limit_source=iteration_limit_source,
        restart_after_iterations=restart_after,
        system_limit_applied=system_limit_applied,
        system_limit_reason=system_limit_reason,
        repair=repair_value,
        acceptance=acceptance_value,
        neighborhoods=validated_neighborhoods,
        candidate_strategy_family=candidate_strategy_family,
        candidate_strategy_families=candidate_strategy_families,
        candidate_construction=candidate_construction,
        dispatch_mode=effective_dispatch_mode,
        dispatch_rule=str(dispatch_rule or "").strip().lower(),
        ortools_warmstart_enabled=ortools_warmstart_enabled,
        strict_mode=bool(strict_mode),
        validation_status="ok",
        message=message,
    )


__all__ = [
    "ALLOWED_ACCEPTANCES",
    "ALLOWED_NEIGHBORHOODS",
    "ALLOWED_PROFILES",
    "ALLOWED_REPAIRS",
    "CANDIDATE_PROFILE_SCHEMA_VERSION",
    "CandidateProfile",
    "PROFILE_BASELINE",
    "PROFILE_GRASP_IG",
    "PROFILE_MULTI_START_LOCAL_SEARCH",
    "build_candidate_profile",
    "derive_grasp_ig_limits",
    "derive_iteration_limits",
]
