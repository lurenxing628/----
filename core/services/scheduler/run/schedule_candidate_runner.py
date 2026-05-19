from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, is_dataclass, replace
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot

from .schedule_candidate_health import CandidateHealth, evaluate_candidate_health, unavailable_health
from .schedule_candidate_selection import CandidateSelectionResult, select_candidate_plan
from .schedule_candidate_specs import (
    CANDIDATE_KIND_BASELINE,
    CANDIDATE_KIND_CRITICAL_CHAIN,
    CandidateRunSpec,
    generate_candidate_specs,
)
from .schedule_graph_report import prepare_schedule_graph_for_dispatch
from .schedule_optimizer import optimize_schedule

CANDIDATE_STATUS_COMPLETED = "completed"
CANDIDATE_STATUS_FAILED = "failed"
CANDIDATE_STATUS_SKIPPED = "skipped"


class CandidateTrialFailure(RuntimeError):
    """单个候选方案可记录为 failed 的运行失败。"""


@dataclass(frozen=True)
class CandidatePlan:
    sequence: int
    candidate_key: str
    kind: str
    label: str
    status: str
    score: Optional[Tuple[float, ...]]
    graph_critical_weight: int
    graph_impact_weight: int
    graph_downstream_weight: int
    results: List[Any] = field(default_factory=list)
    summary: Any = None
    metrics: Any = None
    health: Optional[CandidateHealth] = None
    graph_analysis_public: Optional[Dict[str, Any]] = None
    graph_analysis_diagnostics: Optional[Dict[str, Any]] = None
    used_strategy: Any = None
    used_params: Dict[str, Any] = field(default_factory=dict)
    best_order: List[str] = field(default_factory=list)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    improvement_trace: List[Dict[str, Any]] = field(default_factory=list)
    algo_mode: str = ""
    objective_name: str = ""
    algo_stats: Dict[str, Any] = field(default_factory=dict)
    time_budget_seconds: int = 0
    sort_strategy: str = ""
    dispatch_mode: str = ""
    dispatch_rule: str = ""
    objective: str = ""
    failure_reason: Optional[str] = None
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class CandidateComparisonOutcome:
    candidates: List[CandidatePlan]
    selection: CandidateSelectionResult
    planned_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    time_budget_reached: bool
    selection_policy: str
    run_time_budget_seconds: Optional[float]


@dataclass(frozen=True)
class _CandidateRunArtifacts:
    candidate_cfg: Any
    graph_preparation: Any
    outcome: Any


class _CandidateTrialConfigService:
    def __init__(self, base_cfg_svc: Any, cfg: Any) -> None:
        self._base_cfg_svc = base_cfg_svc
        self.VALID_STRATEGIES = (str(cfg.sort_strategy).strip().lower(),)
        self.VALID_DISPATCH_MODES = (str(cfg.dispatch_mode).strip().lower(),)
        self.VALID_DISPATCH_RULES = (str(cfg.dispatch_rule).strip().lower(),)
        self.VALID_OBJECTIVES = (str(cfg.objective).strip().lower(),)
        self.VALID_ALGO_MODES = ("greedy",)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_cfg_svc, name)


def run_candidate_comparison(
    *,
    schedule_input: Any,
    optimize_schedule_fn: Optional[Callable[..., Any]] = None,
    prepare_graph_fn: Optional[Callable[[Any], Any]] = None,
    clock: Optional[Callable[[], float]] = None,
    run_time_budget_seconds: Optional[float] = None,
    weight_count: int = 5,
    selection_policy: str = "balanced",
    graph_overdue_tolerance_count: int = 1,
    graph_tardiness_tolerance_ratio: float = 0.10,
    strict_mode: bool = False,
    logger: Any = None,
) -> CandidateComparisonOutcome:
    now = clock or time.time
    optimize = optimize_schedule_fn or optimize_schedule
    prepare_graph = prepare_graph_fn or prepare_schedule_graph_for_dispatch
    cfg = ensure_schedule_config_snapshot(schedule_input.cfg, strict_mode=bool(strict_mode))
    specs = generate_candidate_specs(
        weight_count=weight_count,
        base_critical_weight=int(cfg.graph_critical_weight),
        base_impact_weight=int(cfg.graph_impact_weight),
    )
    total_budget = _resolve_total_budget(run_time_budget_seconds, cfg=cfg)
    started = now()
    deadline = started + total_budget if math.isfinite(total_budget) else float("inf")

    candidates, time_budget_reached = _run_candidate_plans(
        specs,
        schedule_input=schedule_input,
        base_cfg=cfg,
        optimize_schedule_fn=optimize,
        prepare_graph_fn=prepare_graph,
        strict_mode=bool(strict_mode),
        logger=logger,
        now=now,
        deadline=deadline,
    )

    selection = select_candidate_plan(
        candidates,
        policy=selection_policy,
        graph_overdue_tolerance_count=graph_overdue_tolerance_count,
        graph_tardiness_tolerance_ratio=graph_tardiness_tolerance_ratio,
    )
    return _comparison_outcome(
        specs=specs,
        candidates=candidates,
        selection=selection,
        time_budget_reached=time_budget_reached,
        selection_policy=selection_policy,
        total_budget=total_budget,
    )


def _run_candidate_plans(
    specs: List[CandidateRunSpec],
    *,
    schedule_input: Any,
    base_cfg: Any,
    optimize_schedule_fn: Callable[..., Any],
    prepare_graph_fn: Callable[[Any], Any],
    strict_mode: bool,
    logger: Any,
    now: Callable[[], float],
    deadline: float,
) -> Tuple[List[CandidatePlan], bool]:
    candidates: List[CandidatePlan] = []
    baseline_results: List[Any] = []
    time_budget_reached = False
    for spec in specs:
        if now() >= deadline:
            time_budget_reached = True
            candidates.append(_skipped_plan(spec, failure_reason="candidate_time_budget_reached"))
            continue
        plan = _run_candidate_with_failure_capture(
            spec,
            schedule_input=schedule_input,
            base_cfg=base_cfg,
            optimize_schedule_fn=optimize_schedule_fn,
            prepare_graph_fn=prepare_graph_fn,
            strict_mode=strict_mode,
            logger=logger,
            baseline_results=baseline_results,
            now=now,
        )
        candidates.append(plan)
        baseline_results = _next_baseline_results(baseline_results, plan)
    return candidates, time_budget_reached


def _run_candidate_with_failure_capture(
    spec: CandidateRunSpec,
    *,
    schedule_input: Any,
    base_cfg: Any,
    optimize_schedule_fn: Callable[..., Any],
    prepare_graph_fn: Callable[[Any], Any],
    strict_mode: bool,
    logger: Any,
    baseline_results: List[Any],
    now: Callable[[], float],
) -> CandidatePlan:
    candidate_started = now()
    try:
        plan = _run_single_candidate(
            spec,
            schedule_input=schedule_input,
            base_cfg=base_cfg,
            optimize_schedule_fn=optimize_schedule_fn,
            prepare_graph_fn=prepare_graph_fn,
            strict_mode=strict_mode,
            logger=logger,
            baseline_results=baseline_results,
        )
    except CandidateTrialFailure as exc:
        return _failed_plan(spec, exc, elapsed_seconds=now() - candidate_started)
    return replace(plan, elapsed_seconds=now() - candidate_started)


def _next_baseline_results(current: List[Any], plan: CandidatePlan) -> List[Any]:
    if plan.kind == CANDIDATE_KIND_BASELINE and plan.status == CANDIDATE_STATUS_COMPLETED:
        return list(plan.results or [])
    return current


def _comparison_outcome(
    *,
    specs: List[CandidateRunSpec],
    candidates: List[CandidatePlan],
    selection: CandidateSelectionResult,
    time_budget_reached: bool,
    selection_policy: str,
    total_budget: float,
) -> CandidateComparisonOutcome:
    return CandidateComparisonOutcome(
        candidates=list(candidates),
        selection=selection,
        planned_count=int(len(specs)),
        completed_count=_count_candidates(candidates, CANDIDATE_STATUS_COMPLETED),
        failed_count=_count_candidates(candidates, CANDIDATE_STATUS_FAILED),
        skipped_count=_count_candidates(candidates, CANDIDATE_STATUS_SKIPPED),
        time_budget_reached=bool(time_budget_reached),
        selection_policy=str(selection_policy),
        run_time_budget_seconds=_public_budget(total_budget),
    )


def _count_candidates(candidates: List[CandidatePlan], status: str) -> int:
    return sum(1 for candidate in candidates if candidate.status == status)


def _run_single_candidate(
    spec: CandidateRunSpec,
    *,
    schedule_input: Any,
    base_cfg: Any,
    optimize_schedule_fn: Callable[..., Any],
    prepare_graph_fn: Callable[[Any], Any],
    strict_mode: bool,
    logger: Any,
    baseline_results: List[Any],
) -> CandidatePlan:
    artifacts = _run_candidate_optimization(
        spec,
        schedule_input=schedule_input,
        base_cfg=base_cfg,
        optimize_schedule_fn=optimize_schedule_fn,
        prepare_graph_fn=prepare_graph_fn,
        strict_mode=strict_mode,
        logger=logger,
    )
    health = _candidate_health(
        spec,
        baseline_results=baseline_results,
        outcome=artifacts.outcome,
        graph_preparation=artifacts.graph_preparation,
    )
    return _candidate_plan_from_artifacts(spec, artifacts=artifacts, health=health)


def _run_candidate_optimization(
    spec: CandidateRunSpec,
    *,
    schedule_input: Any,
    base_cfg: Any,
    optimize_schedule_fn: Callable[..., Any],
    prepare_graph_fn: Callable[[Any], Any],
    strict_mode: bool,
    logger: Any,
) -> _CandidateRunArtifacts:
    candidate_cfg = _candidate_cfg(base_cfg, spec)
    candidate_input = _replace_schedule_input_cfg(schedule_input, cfg=candidate_cfg)
    graph_preparation = prepare_graph_fn(candidate_input)
    trial_cfg_svc = _CandidateTrialConfigService(schedule_input.cfg_svc, candidate_cfg)
    outcome = optimize_schedule_fn(
        calendar_service=schedule_input.cal_svc,
        cfg_svc=trial_cfg_svc,
        cfg=candidate_cfg,
        algo_ops_to_schedule=schedule_input.algo_ops_to_schedule,
        batches=schedule_input.batches,
        start_dt=schedule_input.start_dt_norm,
        end_date=schedule_input.end_date_norm,
        downtime_map=schedule_input.downtime_map,
        seed_results=schedule_input.seed_results,
        resource_pool=schedule_input.resource_pool,
        version=int(schedule_input.optimizer_seed_version),
        logger=logger,
        readiness_gate_enabled=bool(schedule_input.readiness_gate_enabled),
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_preparation.graph_ready_context,
        graph_dispatch_mode_override=graph_preparation.graph_dispatch_mode_override,
    )
    return _CandidateRunArtifacts(candidate_cfg=candidate_cfg, graph_preparation=graph_preparation, outcome=outcome)


def _candidate_plan_from_artifacts(
    spec: CandidateRunSpec,
    *,
    artifacts: _CandidateRunArtifacts,
    health: CandidateHealth,
) -> CandidatePlan:
    candidate_cfg = artifacts.candidate_cfg
    graph_preparation = artifacts.graph_preparation
    outcome = artifacts.outcome
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_COMPLETED,
        score=_candidate_score(outcome),
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        results=list(outcome.results or []),
        summary=getattr(outcome, "summary", None),
        metrics=getattr(outcome, "metrics", None),
        health=health,
        graph_analysis_public=_dict_or_none(getattr(graph_preparation, "graph_analysis_public", None)),
        graph_analysis_diagnostics=_dict_or_none(getattr(graph_preparation, "graph_analysis_diagnostics", None)),
        used_strategy=getattr(outcome, "used_strategy", None),
        used_params=dict(getattr(outcome, "used_params", None) or {}),
        best_order=_string_list(getattr(outcome, "best_order", None)),
        attempts=_dict_list(getattr(outcome, "attempts", None)),
        improvement_trace=_dict_list(getattr(outcome, "improvement_trace", None)),
        algo_mode=str(getattr(outcome, "algo_mode", None) or ""),
        objective_name=str(getattr(outcome, "objective_name", None) or ""),
        algo_stats=dict(getattr(outcome, "algo_stats", None) or {}),
        time_budget_seconds=int(getattr(outcome, "time_budget_seconds", None) or 0),
        sort_strategy=str(candidate_cfg.sort_strategy),
        dispatch_mode=str(candidate_cfg.dispatch_mode),
        dispatch_rule=str(candidate_cfg.dispatch_rule),
        objective=str(candidate_cfg.objective),
    )


def _candidate_score(outcome: Any) -> Tuple[float, ...]:
    return tuple(float(item) for item in tuple(outcome.best_score))


def _string_list(value: Any) -> List[str]:
    return [str(item) for item in list(value or [])]


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    return [dict(item) for item in list(value or []) if isinstance(item, dict)]


def _candidate_cfg(base_cfg: Any, spec: CandidateRunSpec) -> Any:
    graph_mode = "on" if spec.graph_enabled else "off"
    return replace(
        base_cfg,
        algo_mode="greedy",
        graph_analysis_mode=graph_mode,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
    )


def _replace_schedule_input_cfg(schedule_input: Any, *, cfg: Any) -> Any:
    if is_dataclass(schedule_input) and not isinstance(schedule_input, type):
        return replace(cast(Any, schedule_input), cfg=cfg)
    if hasattr(schedule_input, "__dict__"):
        data = dict(vars(schedule_input))
        data["cfg"] = cfg
        return SimpleNamespace(**data)
    raise TypeError("schedule_input 必须是 dataclass 或普通对象，才能构造候选级输入。")


def _candidate_health(
    spec: CandidateRunSpec,
    *,
    baseline_results: List[Any],
    outcome: Any,
    graph_preparation: Any,
) -> CandidateHealth:
    if spec.kind != CANDIDATE_KIND_CRITICAL_CHAIN:
        return unavailable_health("baseline")
    if not baseline_results:
        return unavailable_health("baseline_result_unavailable")
    graph_metrics = _graph_health_context_payload(graph_preparation)
    return evaluate_candidate_health(
        baseline_results=baseline_results,
        candidate_results=list(outcome.results or []),
        graph_metrics=graph_metrics,
    )


def _graph_health_context_payload(graph_preparation: Any) -> Dict[str, Any]:
    health_context = getattr(graph_preparation, "graph_health_context", None)
    if isinstance(health_context, dict):
        return dict(health_context)
    return {}


def _resolve_total_budget(run_time_budget_seconds: Optional[float], *, cfg: Any) -> float:
    if run_time_budget_seconds is None:
        return float(cfg.time_budget_seconds)
    if isinstance(run_time_budget_seconds, bool):
        raise ValidationError("候选比较总时间预算必须是数字。", field="candidate_time_budget_seconds")
    budget = float(run_time_budget_seconds)
    if budget < 0:
        raise ValidationError("候选比较总时间预算不能为负数。", field="candidate_time_budget_seconds")
    return budget


def _public_budget(total_budget: float) -> Optional[float]:
    if not math.isfinite(total_budget):
        return None
    return float(total_budget)


def _skipped_plan(spec: CandidateRunSpec, *, failure_reason: str) -> CandidatePlan:
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_SKIPPED,
        score=None,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        failure_reason=failure_reason,
    )


def _failed_plan(spec: CandidateRunSpec, exc: Exception, *, elapsed_seconds: float) -> CandidatePlan:
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_FAILED,
        score=None,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        failure_reason=str(exc),
        elapsed_seconds=float(elapsed_seconds),
    )


def _dict_or_none(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("图分析结果必须是 dict 或 None。")


__all__ = [
    "CANDIDATE_STATUS_COMPLETED",
    "CANDIDATE_STATUS_FAILED",
    "CANDIDATE_STATUS_SKIPPED",
    "CandidateComparisonOutcome",
    "CandidatePlan",
    "CandidateTrialFailure",
    "run_candidate_comparison",
]
