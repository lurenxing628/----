from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot

from .optimizer_search_budget import (
    CandidateBudgetFeedback,
    SearchBudget,
    SearchBudgetExhausted,
    allocate_candidate_budget,
)
from .schedule_candidate_dedup import CandidateInputLedger
from .schedule_candidate_plan import (
    CANDIDATE_STATUS_COMPLETED,
    CANDIDATE_STATUS_FAILED,
    CANDIDATE_STATUS_SKIPPED,
    CandidateComparisonOutcome,
    CandidatePlan,
    CandidateRunArtifacts,
    CandidateTrialFailure,
    candidate_plan_from_artifacts,
    failed_plan,
    skipped_plan,
    with_input_certification,
)
from .schedule_candidate_runtime_helpers import (
    _candidate_cfg,
    _candidate_health,
    _candidate_score,
    _dict_list,
    _dict_or_none,
    _public_budget,
    _replace_schedule_input_cfg,
    _resolve_total_budget,
    _string_list,
)
from .schedule_candidate_selection import CandidateSelectionResult, select_candidate_plan
from .schedule_candidate_specs import (
    CANDIDATE_KIND_BASELINE,
    CandidateRunSpec,
    generate_candidate_specs,
)
from .schedule_graph_report import make_cached_graph_preparation_fn
from .schedule_optimizer import optimize_schedule


class _CandidateTrialConfigService:
    """Config view of one candidate trial: comparability locks only, never the optimizer's rule pool.

    Candidates must differ in graph weights alone, so the sort strategy, dispatch mode, objective
    and algorithm mode are pinned to the configured values. The SGS dispatch rule pool is the
    optimizer's own search dimension (multi-start rules and the rule neighborhood) and stays the
    registry pool; the rule a plan finally adopts is reported on the plan itself.
    """

    def __init__(self, base_cfg_svc: Any, cfg: Any) -> None:
        self._base_cfg_svc = base_cfg_svc
        self.VALID_STRATEGIES = (str(cfg.sort_strategy).strip().lower(),)
        self.VALID_DISPATCH_MODES = (str(cfg.dispatch_mode).strip().lower(),)
        self.VALID_OBJECTIVES = (str(cfg.objective).strip().lower(),)
        self.VALID_ALGO_MODES = (str(cfg.algo_mode).strip().lower(),)

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
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> CandidateComparisonOutcome:
    now = clock or time.monotonic
    optimize = optimize_schedule_fn or optimize_schedule
    prepare_graph = prepare_graph_fn if prepare_graph_fn is not None else make_cached_graph_preparation_fn()
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
        on_progress=on_progress,
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
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[CandidatePlan], bool]:
    candidates: List[CandidatePlan] = []
    baseline_results: List[Any] = []
    feedback = CandidateBudgetFeedback(str(base_cfg.objective))
    ledger = CandidateInputLedger(schedule_input=schedule_input, base_cfg=base_cfg, prepare_graph_fn=prepare_graph_fn)
    time_budget_reached = False
    # Progress counts finished candidate plans (computed, reused or skipped) out of the planned total, in loop order.
    report = on_progress if callable(on_progress) else (lambda done, total: None)
    for index, spec in enumerate(specs):
        candidate_started = now()
        # A previously certified twin needs no preparation or decoder budget. Finish publishing
        # those already-computed plans even when the last non-preemptible decode crossed the deadline.
        twin = ledger.completed_twin(spec)
        if candidate_started >= deadline:
            time_budget_reached = True
            if twin is None:
                candidates.append(skipped_plan(spec, failure_reason="candidate_time_budget_reached"))
                report(len(candidates), len(specs))
                continue
        if spec.graph_enabled and twin is None:
            # Prepare every remaining graph plan inside the first graph plan's slice: the weight-independent
            # core is shared and each projection is cheap, and knowing which tiers have identical optimizer
            # inputs lets duplicates reuse a sibling while the budget is split among plans needing a search.
            ledger.prepare_graph_specs(specs[index:])
            twin = ledger.completed_twin(spec)
        if twin is not None:
            plan = ledger.reuse(
                spec, twin, baseline_results=baseline_results,
                elapsed_seconds=now() - candidate_started,
            )
            feedback.observe_reused(plan)
        else:
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
                prepared=ledger.prepared(spec),
                search_budget=allocate_candidate_budget(
                    clock=now, started_at=candidate_started, deadline=deadline,
                    remaining_candidates=ledger.distinct_remaining(specs[index:]), feedback=feedback,
                ),
            )
            # Certify before the ledger keeps the plan: a reused sibling inherits the twin's record.
            plan = with_input_certification(plan, ledger.certification(spec), logger=logger)
            ledger.observe(spec, plan, completed=plan.status == CANDIDATE_STATUS_COMPLETED)
            feedback.observe(plan)
        candidates.append(plan)
        report(len(candidates), len(specs))
        baseline_results = _next_baseline_results(baseline_results, plan)
    return candidates, time_budget_reached or now() >= deadline


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
    search_budget: SearchBudget,
    prepared: Any = None,
) -> CandidatePlan:
    candidate_started = search_budget.started_at
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
            search_budget=search_budget,
            prepared=prepared,
        )
    # 仅显式候选失败和未启动解码的预算耗尽转换状态；其余 ValidationError/RuntimeError/TypeError 继续上抛。
    # 这是 b81f8b3f 收窄后的护栏:绝不能以"统一/简化"名义改回 except Exception,
    # 否则复活被治理掉的"未知异常静默转 failed candidate"静默吞错(踩灵魂线)。
    except CandidateTrialFailure as exc:
        return failed_plan(spec, exc, elapsed_seconds=now() - candidate_started)
    except SearchBudgetExhausted:
        return replace(
            skipped_plan(spec, failure_reason="candidate_time_budget_reached"),
            elapsed_seconds=max(now() - candidate_started, 0.0),
        )
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
        skipped_candidate_labels=_skipped_candidate_labels(candidates),
        baseline_missing_or_failed=_baseline_missing_or_failed(candidates),
        reused_count=sum(1 for candidate in candidates if candidate.reused_from_candidate_key),
    )


def _count_candidates(candidates: List[CandidatePlan], status: str) -> int:
    return sum(1 for candidate in candidates if candidate.status == status)


def _skipped_candidate_labels(candidates: List[CandidatePlan]) -> List[str]:
    return [
        str(candidate.label)
        for candidate in candidates
        if candidate.status == CANDIDATE_STATUS_SKIPPED and str(candidate.label or "").strip()
    ]


def _baseline_missing_or_failed(candidates: List[CandidatePlan]) -> bool:
    # O25 四态语义（勿当死分支清理）：missing 半边（空/无 baseline 候选→True）生产可达，是「没有基准
    # 方案」真实告警源头；failed 半边不可达但随枚举契约保留。下游 workbench/helpers 消费分支禁裸删。
    for candidate in candidates:
        if candidate.kind == CANDIDATE_KIND_BASELINE:
            return candidate.status != CANDIDATE_STATUS_COMPLETED
    return True


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
    search_budget: SearchBudget,
    prepared: Any = None,
) -> CandidatePlan:
    artifacts = _run_candidate_optimization(
        spec,
        schedule_input=schedule_input,
        base_cfg=base_cfg,
        optimize_schedule_fn=optimize_schedule_fn,
        prepare_graph_fn=prepare_graph_fn,
        strict_mode=strict_mode,
        logger=logger,
        search_budget=search_budget,
        prepared=prepared,
    )
    health = _candidate_health(
        spec,
        baseline_results=baseline_results,
        outcome=artifacts.outcome,
        graph_preparation=artifacts.graph_preparation,
    )
    return candidate_plan_from_artifacts(spec, artifacts=artifacts, health=health)


def _run_candidate_optimization(
    spec: CandidateRunSpec,
    *,
    schedule_input: Any,
    base_cfg: Any,
    optimize_schedule_fn: Callable[..., Any],
    prepare_graph_fn: Callable[[Any], Any],
    strict_mode: bool,
    logger: Any,
    search_budget: SearchBudget,
    prepared: Any = None,
) -> CandidateRunArtifacts:
    if prepared is None:
        candidate_cfg = _candidate_cfg(base_cfg, spec)
        graph_preparation = prepare_graph_fn(_replace_schedule_input_cfg(schedule_input, cfg=candidate_cfg))
    else:
        candidate_cfg, graph_preparation = prepared
    search_budget.require_available()
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
        search_budget=search_budget,
    )
    return CandidateRunArtifacts(candidate_cfg=candidate_cfg, graph_preparation=graph_preparation, outcome=outcome)


__all__ = ["CANDIDATE_STATUS_COMPLETED", "CANDIDATE_STATUS_FAILED", "CANDIDATE_STATUS_SKIPPED", "CandidateComparisonOutcome", "CandidatePlan", "CandidateTrialFailure", "run_candidate_comparison"]
