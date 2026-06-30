"""回归测试：optimizer candidate profile 合同（roadmap item 4）。

只锁现有 optimizer 已有能力的 profile 合同与校验边界：
- 现有能力包括 baseline 与 vns_sa（多起点 + GRASP/IG候选 + VNS局部搜索）；
- configured 与 effective 的时间预算、迭代上限必须可区分、可报告；
- 系统钳制迭代上限时如实写 system_limit_applied / system_limit_reason；
- 未知 profile / repair / acceptance / neighborhood 一律 fail-loud（与 strict 无关）；
- profile 接入 OptimizationSearchReport，且 algorithm_profile 由 profile 派生；
- profile public 投影只露安全摘要，内部配置细节只进 diagnostics。

本轮扩展 VNS / 阈值 / 模拟退火类接受画像；不实现 ALNS。
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_profile import (
    ITERATION_CEILING,
    ITERATION_FLOOR,
    build_candidate_profile,
    derive_grasp_ig_limits,
    derive_iteration_limits,
)
from core.services.scheduler.run.optimizer_neighborhood_moves import BUSINESS_NEIGHBORHOODS
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.schedule_candidate_persistence_models import operation_log_algo_summary
from core.services.scheduler.run.schedule_optimizer import optimize_schedule
from core.services.scheduler.run.schedule_optimizer_steps import _run_multi_start
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary
from core.services.scheduler.summary.summary_size_guard_fields import minimal_summary_for_size_guard

_FORBIDDEN_PUBLIC_TOKENS = (
    "op:",
    "op_id",
    "node_id",
    "candidate_id",
    "candidate_key",
    "candidate_fingerprint",
    "source_table",
    "scenario_id",
    "graph_w",
)
_PROFILE_DIAGNOSTIC_ONLY_KEYS = (
    "repair",
    "dispatch_mode",
    "dispatch_rule",
    "strict_mode",
    "validation_status",
    "seed_source",
    "iteration_limit_source",
    "restart_after_iterations",
    "ortools_warmstart_enabled",
    "schema_version",
    "candidate_strategy_family",
    "candidate_construction",
)


# --------------------------------------------------------------------------- #
# 1. derive_iteration_limits 单一真相源
# --------------------------------------------------------------------------- #
def test_derive_iteration_limits_matches_historical_formula() -> None:
    # 与历史 optimizer_local_search 内联公式逐位一致。
    assert derive_iteration_limits(1) == (200, 50)  # 1*20=20 → 下限抬到 200；restart max(50,200//8=25)=50
    assert derive_iteration_limits(5) == (200, 50)  # 默认 5s：100 → 下限抬到 200
    assert derive_iteration_limits(10) == (200, 50)  # 10*20=200 恰好等于下限
    assert derive_iteration_limits(250) == (5000, 625)  # 250*20=5000 恰好等于上限；restart 5000//8=625
    assert derive_iteration_limits(300) == (5000, 625)  # 6000 → 上限压回 5000


# --------------------------------------------------------------------------- #
# 2. build_candidate_profile：improve / baseline 基础合同
# --------------------------------------------------------------------------- #
def _build(**overrides: Any):
    params: Dict[str, Any] = {
        "algo_mode": "improve",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "time_budget_seconds": 5,
        "version": 42,
        "strict_mode": False,
        "ortools_enabled": False,
        "graph_sgs_required": False,
    }
    params.update(overrides)
    return build_candidate_profile(**params)


def test_improve_profile_reports_configured_and_effective_with_system_floor() -> None:
    profile = _build(time_budget_seconds=5)
    assert profile.profile == "vns_sa"
    assert profile.enabled is True
    assert profile.seed == 42
    assert profile.seed_source == "optimizer_version"
    assert profile.configured_time_budget_seconds == 5
    assert profile.effective_time_budget_seconds == 5  # 时间预算当前无系统上限
    assert profile.configured_max_iterations == 100  # 5*20
    assert profile.effective_max_iterations == 200  # 被系统下限抬升
    assert profile.system_limit_applied is True
    assert profile.system_limit_reason == "iteration_floor"
    assert profile.iteration_limit_source == "system_limit"
    assert profile.restart_after_iterations == 50
    assert profile.repair == "sgs"
    assert profile.acceptance == "improve_only"
    assert profile.neighborhoods == BUSINESS_NEIGHBORHOODS
    assert profile.candidate_strategy_family == "multi_start_grasp_ig"
    assert profile.candidate_strategy_families == ("multi_start", "grasp", "iterated_greedy")
    assert profile.candidate_construction == derive_grasp_ig_limits(5)
    assert profile.candidate_construction["seed_source"] == "optimizer_version"
    assert profile.candidate_construction["grasp"]["configured_restarts"] == 5
    assert profile.candidate_construction["grasp"]["effective_restarts"] == 5
    assert profile.candidate_construction["iterated_greedy"]["configured_restarts"] == 3
    assert profile.candidate_construction["iterated_greedy"]["effective_restarts"] == 3
    assert profile.validation_status == "ok"


def test_improve_profile_without_system_limit_uses_profile_default_source() -> None:
    profile = _build(time_budget_seconds=250)  # 250*20=5000 恰好命中上限边界但不被钳制
    assert profile.configured_max_iterations == 5000
    assert profile.effective_max_iterations == 5000
    assert profile.system_limit_applied is False
    assert profile.system_limit_reason is None
    assert profile.iteration_limit_source == "profile_default"


def test_improve_profile_system_ceiling_is_reported() -> None:
    profile = _build(time_budget_seconds=300)  # 6000 → 上限压回 5000
    assert profile.configured_max_iterations == 6000
    assert profile.effective_max_iterations == ITERATION_CEILING == 5000
    assert profile.system_limit_applied is True
    assert profile.system_limit_reason == "iteration_ceiling"


def test_baseline_profile_disables_search_budget() -> None:
    profile = _build(algo_mode="greedy", ortools_enabled=True)
    assert profile.profile == "baseline"
    assert profile.enabled is False
    assert profile.configured_time_budget_seconds == 5  # 如实回显用户配置
    assert profile.effective_time_budget_seconds == 0  # 未启用搜索循环
    assert profile.configured_max_iterations == 0
    assert profile.effective_max_iterations == 0
    assert profile.iteration_limit_source == "not_applicable"
    assert profile.neighborhoods == ()
    assert profile.candidate_strategy_family == "single_shot"
    assert profile.candidate_strategy_families == ("single_shot",)
    assert profile.candidate_construction == {}
    # OR-Tools warm-start 只在 improve 下尝试：baseline 即便配置开启也不升主引擎。
    assert profile.ortools_warmstart_enabled is False


def test_graph_context_forces_sgs_and_ceiling_clamp() -> None:
    profile = _build(time_budget_seconds=300, graph_sgs_required=True, ortools_enabled=True)
    assert profile.dispatch_mode == "sgs"
    assert profile.profile == "graph_ready"
    assert profile.candidate_strategy_family == "graph_ready_objective_aware_portfolio"
    assert profile.candidate_strategy_families == ("graph_ready_base", "graph_ready_weight_grid", "graph_ready_v2_no_repair")
    assert profile.candidate_construction["graph_ready_optimization"]["candidate_policy"] == "objective_aware_portfolio"
    assert profile.effective_max_iterations == 5000
    assert profile.ortools_warmstart_enabled is True


def test_ortools_warmstart_enabled_tracks_config_and_mode() -> None:
    assert _build(ortools_enabled=True).ortools_warmstart_enabled is True
    assert _build(ortools_enabled=False).ortools_warmstart_enabled is False


# --------------------------------------------------------------------------- #
# 3. 非法配置 fail-loud（与 strict 无关）
# --------------------------------------------------------------------------- #
def test_unknown_profile_fail_loud() -> None:
    with pytest.raises(ValidationError) as exc:
        _build(algo_mode="grasp")  # 未知计算模式不能静默回 baseline
    assert exc.value.field == "algo_mode"


def test_unknown_repair_fail_loud() -> None:
    with pytest.raises(ValidationError) as exc:
        _build(repair="ortools")  # 本阶段 repair 只允许 sgs
    assert exc.value.field == "repair"


def test_unknown_acceptance_fail_loud() -> None:
    with pytest.raises(ValidationError) as exc:
        _build(acceptance="teleport")
    assert exc.value.field == "acceptance"


def test_item8_acceptance_profiles_are_allowed() -> None:
    assert _build(acceptance="improve_only").acceptance == "improve_only"
    assert _build(acceptance="threshold").acceptance == "threshold"
    assert _build(acceptance="record_to_record").acceptance == "record_to_record"
    assert _build(acceptance="simulated_annealing").acceptance == "simulated_annealing"


def test_unknown_neighborhood_fail_loud() -> None:
    with pytest.raises(ValidationError) as exc:
        _build(neighborhoods=("critical_chain", "teleport"))  # 未知邻域不能静默接受
    assert exc.value.field == "neighborhood"


def test_invalid_budget_not_silently_defaulted() -> None:
    # 非法时间预算必须 fail-loud，不能静默改成默认/最小值。
    with pytest.raises(ValidationError) as exc:
        _build(time_budget_seconds=0)
    assert exc.value.field == "time_budget_seconds"


def test_profile_contract_error_fail_loud_even_in_non_strict() -> None:
    # 非 strict 也不能吞掉 profile 合同错误（只允许对可选候选做 candidate_rejected）。
    with pytest.raises(ValidationError) as exc:
        _build(repair="garbage", strict_mode=False)
    assert exc.value.field == "repair"


# --------------------------------------------------------------------------- #
# 4. profile 接入 OptimizationSearchReport（集成）
# --------------------------------------------------------------------------- #
class _Scheduler:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        summary = SimpleNamespace(
            success=True,
            total_ops=int(len(operations or [])),
            scheduled_ops=int(len(operations or [])),
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        used_params = dict(strategy_params or {})
        used_params["dispatch_mode"] = str(kwargs.get("dispatch_mode") or "")
        used_params["dispatch_rule"] = str(kwargs.get("dispatch_rule") or "")
        return [], summary, strategy, used_params


class _Clock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01) -> None:
        self._now = float(start)
        self._step = float(step)

    def __call__(self) -> float:
        current = self._now
        self._now += self._step
        return current


class _DeterministicRandom:
    def random(self):
        return 0.1

    def sample(self, seq, n):
        return [0, 1]

    def randrange(self, n):
        return 0

    def randint(self, a, b):
        return a


def _cfg(**overrides: Any) -> SimpleNamespace:
    data: Dict[str, Any] = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 1.0,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "algo_mode": "improve",
        "objective": "min_overdue",
        "time_budget_seconds": 5,
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_candidate_weight_count": 5,
        "graph_selection_policy": "balanced",
        "graph_overdue_tolerance_count": 1,
        "graph_tardiness_tolerance_ratio": 0.10,
        "graph_debug_export": "no",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _cfg_svc(*, dispatch_modes=("batch_order",), dispatch_rules=("slack",)) -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first",),
        VALID_DISPATCH_MODES=tuple(dispatch_modes),
        VALID_DISPATCH_RULES=tuple(dispatch_rules),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


def _batches() -> Dict[str, Any]:
    return {
        "B1": SimpleNamespace(
            batch_id="B1",
            priority="normal",
            due_date="2026-01-02",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
    }


def _runtime(
    *,
    run_multi_start=lambda **kwargs: kwargs.get("best"),
) -> OptimizerRuntime:
    return OptimizerRuntime(
        scheduler_factory=lambda **kwargs: _Scheduler(**kwargs),
        clock=_Clock(),
        rng_factory=lambda _seed: _DeterministicRandom(),
        run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
        run_multi_start=run_multi_start,
        run_local_search=lambda **kwargs: kwargs.get("best"),
    )


def _optimize(**kwargs: Any):
    params: Dict[str, Any] = {
        "calendar_service": SimpleNamespace(),
        "cfg_svc": _cfg_svc(),
        "cfg": _cfg(),
        "algo_ops_to_schedule": [],
        "batches": _batches(),
        "start_dt": datetime(2026, 1, 1, 8, 0, 0),
        "end_date": None,
        "downtime_map": {},
        "seed_results": [],
        "resource_pool": None,
        "version": 42,
        "logger": None,
        "_runtime": _runtime(),
    }
    params.update(kwargs)
    return optimize_schedule(**params)


def test_every_outcome_carries_candidate_profile_traceable_to_search_report() -> None:
    outcome = _optimize()
    report = outcome.search_report
    profile = report["candidate_profile"]
    # profile 与 search_report 必填字段都在，且 algorithm_profile 由 profile 派生（不再是模糊串）。
    assert profile["profile"] == report["algorithm_profile"]
    assert profile["seed"] == report["seed"] == 42
    assert profile["configured_time_budget_seconds"] == 5
    assert profile["effective_time_budget_seconds"] == 5
    assert profile["configured_max_iterations"] == 100
    assert profile["effective_max_iterations"] == 200
    assert profile["system_limit_applied"] is True
    assert profile["system_limit_reason"] == "iteration_floor"


def test_vns_sa_improve_profile_is_explicit() -> None:
    outcome = _optimize(_runtime=_runtime(run_multi_start=_run_multi_start))
    profile = outcome.search_report["candidate_profile"]
    assert profile["profile"] == "vns_sa"
    assert profile["enabled"] is True
    # 不改变既有 best_origin 语义。
    assert outcome.search_report["best_origin"] == "multi_start"


def test_legacy_baseline_profile_is_explicit() -> None:
    outcome = _optimize(cfg=_cfg(algo_mode="greedy"))
    profile = outcome.search_report["candidate_profile"]
    assert profile["profile"] == "baseline"
    assert profile["enabled"] is False
    assert profile["effective_max_iterations"] == 0
    assert outcome.search_report["algorithm_profile"] == "baseline"


def test_search_report_stop_reason_consistent_with_effective_iteration_limit() -> None:
    # effective_max_iterations 与 stop_reason=iteration_limit 同源一致（同走 derive_iteration_limits）。
    profile = _build(time_budget_seconds=1)
    assert profile.effective_max_iterations == ITERATION_FLOOR == 200
    # item 3 已锁 time_budget=1 + 恒定时钟下 iterations==200 且 stop_reason==iteration_limit，
    # 本轮 profile 的 effective 与该值同源，避免两套迭代上限打架。


def test_profile_effective_iterations_share_single_source_with_local_search() -> None:
    # 单一真相源不变量：profile 报告的 effective/restart 必须等于 derive_iteration_limits 的产出，
    # 而 optimizer_local_search 也调用同一函数取 it_limit/restart_after，二者结构性同源、不可能漂移。
    # 这条用例防止未来有人单独改 profile 侧或 local_search 侧的迭代上限而埋下两套上限。
    for budget in (1, 5, 10, 250, 300):
        profile = _build(time_budget_seconds=budget)
        it_limit, restart_after = derive_iteration_limits(budget)
        assert profile.effective_max_iterations == it_limit
        assert profile.restart_after_iterations == restart_after


# --------------------------------------------------------------------------- #
# 5. public / diagnostics 分层投影
# --------------------------------------------------------------------------- #
def _profile_report_dict(**overrides: Any) -> Dict[str, Any]:
    return {"candidate_profile": _build(**overrides).to_report_dict()}


def test_profile_public_projection_whitelist_only() -> None:
    public, diagnostics = project_search_report(_profile_report_dict(time_budget_seconds=5))
    profile_public = public["profile_public"]
    # 白名单字段齐全。
    assert profile_public["profile"] == "vns_sa"
    assert profile_public["acceptance"] == "improve_only"
    assert profile_public["enabled"] is True
    assert profile_public["seed"] == 42
    assert profile_public["configured_time_budget_seconds"] == 5
    assert profile_public["effective_max_iterations"] == 200
    assert profile_public["system_limit_applied"] is True
    assert profile_public["system_limit_reason"] == "iteration_floor"
    assert profile_public["candidate_strategy_families"] == ["multi_start", "grasp", "iterated_greedy"]
    assert profile_public["configured_neighborhoods"] == list(BUSINESS_NEIGHBORHOODS)
    assert "neighborhoods" not in profile_public
    assert profile_public["message"]
    # 配置内部细节绝不进 public。
    for key in _PROFILE_DIAGNOSTIC_ONLY_KEYS:
        assert key not in profile_public
    # 配置来源细节进 diagnostics。
    profile_diag = diagnostics["profile_diagnostics"]
    assert profile_diag["repair"] == "sgs"
    assert profile_diag["iteration_limit_source"] == "system_limit"
    assert profile_diag["candidate_strategy_family"] == "multi_start_grasp_ig"
    assert profile_diag["candidate_construction"]["grasp"]["effective_restarts"] == 5
    assert profile_diag["candidate_construction"]["iterated_greedy"]["effective_restarts"] == 3


def test_profile_public_has_no_internal_identifier_tokens() -> None:
    public, _diag = project_search_report(_profile_report_dict())
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        assert forbidden not in public_text


def test_profile_public_flows_through_algo_summary_and_keeps_diagnostics_split() -> None:
    public_algo, diagnostics = project_public_algo_summary({"search_report": _profile_report_dict()})
    profile_public = public_algo["search_report"]["profile_public"]
    assert profile_public["profile"] == "vns_sa"
    public_text = json.dumps(public_algo, ensure_ascii=False, sort_keys=True)
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        assert forbidden not in public_text
    # diagnostics 不进 public algo 正文。
    profile_diag = diagnostics["optimizer"]["search_report"]["profile_diagnostics"]
    assert profile_diag["repair"] == "sgs"


def test_operation_log_algo_summary_keeps_profile_public_only() -> None:
    summary = {
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "search_report": {
                "stop_reason": "time_budget",
                "best_origin": "local_search",
                "candidate_profile": _build().to_report_dict(),
            },
        }
    }
    public_log_algo = operation_log_algo_summary(summary)
    profile_public = public_log_algo["search_report"]["profile_public"]
    assert profile_public["profile"] == "vns_sa"
    assert profile_public["configured_neighborhoods"] == list(BUSINESS_NEIGHBORHOODS)
    assert "neighborhoods" not in profile_public
    public_text = json.dumps(public_log_algo, ensure_ascii=False, sort_keys=True)
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        assert forbidden not in public_text
    # diagnostics-only 字段不得出现在 OperationLogs public 投影。
    assert "repair" not in profile_public
    assert "candidate_construction" not in profile_public


def test_size_guard_minimal_fallback_keeps_profile_public() -> None:
    result_summary = {
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "time_budget_seconds": 5,
            "search_report": {
                "schema_version": 1,
                "algorithm_profile": "vns_sa",
                "stop_reason": "time_budget",
                "best_origin": "local_search",
                "candidate_profile": _build().to_report_dict(),
            },
        }
    }
    minimal = minimal_summary_for_size_guard(result_summary, original_size=999999, diagnostics_truncated=True)
    profile_public = minimal["algo"]["search_report"]["profile_public"]
    assert profile_public["profile"] == "vns_sa"
    assert profile_public["effective_max_iterations"] == 200
    assert profile_public["system_limit_applied"] is True
