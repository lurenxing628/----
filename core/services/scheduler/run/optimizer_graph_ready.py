from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.infrastructure.errors import ValidationError

from .optimizer_candidate_comparison import candidate_is_preferred
from .optimizer_graph_ready_candidates import evaluate_graph_ready_candidate
from .optimizer_graph_ready_context import (
    graph_node_metrics_by_op_id,
    reason_from_validation,
    validate_graph_ready_context,
)
from .optimizer_graph_ready_profiles import (
    GRAPH_READY_BASE_ORIGIN,
    GRAPH_READY_DEFAULT_WEIGHT_PROFILES,
    GRAPH_READY_LOCAL_SEARCH_ORIGIN,
    GRAPH_READY_PHASE,
    GRAPH_READY_REQUIRED_CONTEXT_FIELDS,
    GRAPH_READY_WEIGHT_GRID_ORIGIN,
    GraphReadyWeightProfile,
    default_weight_profiles,
    graph_ready_weight_profile_summary,
)
from .optimizer_graph_ready_reporting import (
    append_graph_attempt,
    append_graph_trace,
    mark_phase_skipped,
    record_rejected_attempt,
)

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


def run_graph_ready_candidates(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Optional[Any],
    clock: Callable[[], float],
    schedule_fn: Callable[..., Any],
    search_report_state: Optional[OptimizationSearchReportState] = None,
    max_weight_profiles: int = 9,
) -> Optional[Dict[str, Any]]:
    skip_reason = _phase_skip_reason(algo_mode=algo_mode, graph_ready_context=graph_ready_context)
    if skip_reason:
        mark_phase_skipped(search_report_state, skip_reason)
        return best

    metrics_by_op_id = _validated_context_metrics(
        graph_ready_context=graph_ready_context,
        algo_ops_to_schedule=algo_ops_to_schedule,
        seed_sr_list=seed_sr_list,
        strict_mode=bool(strict_mode),
        attempts=attempts,
        base_strategy=base_strategy,
        dispatch_rule_cfg=dispatch_rule_cfg,
        search_report_state=search_report_state,
    )
    if metrics_by_op_id is None:
        return best

    _update_graph_ready_profile(search_report_state, max_weight_profiles=max_weight_profiles)

    profiles, _truncated, _reason = default_weight_profiles(max_weight_profiles=max_weight_profiles)
    order = _candidate_order(best, build_order=build_order, base_strategy=base_strategy, base_params=base_params)
    return _run_weight_profiles(
        profiles=profiles,
        best=best,
        version=version,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        base_strategy=base_strategy,
        base_params=base_params,
        dispatch_rule_cfg=dispatch_rule_cfg,
        resource_pool=resource_pool,
        objective_name=objective_name,
        deadline=deadline,
        attempts=attempts,
        improvement_trace=improvement_trace,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        readiness_gate_enabled=readiness_gate_enabled,
        strict_mode=strict_mode,
        graph_ready_context=graph_ready_context,
        metrics_by_op_id=metrics_by_op_id,
        clock=clock,
        schedule_fn=schedule_fn,
        search_report_state=search_report_state,
        order=order,
    )


def _phase_skip_reason(*, algo_mode: str, graph_ready_context: Optional[Any]) -> Optional[str]:
    if graph_ready_context is None:
        return "graph_ready_unavailable"
    if str(algo_mode or "").strip().lower() != "improve":
        return "algo_mode_not_improve"
    return None


def _validated_context_metrics(
    *,
    graph_ready_context: Any,
    algo_ops_to_schedule: List[Any],
    seed_sr_list: List[ScheduleResult],
    strict_mode: bool,
    attempts: List[Dict[str, Any]],
    base_strategy: SortStrategy,
    dispatch_rule_cfg: str,
    search_report_state: Optional[OptimizationSearchReportState],
) -> Optional[Dict[int, Dict[str, Any]]]:
    try:
        validate_graph_ready_context(
            graph_ready_context,
            algo_ops_to_schedule=algo_ops_to_schedule,
            seed_sr_list=seed_sr_list,
        )
        return graph_node_metrics_by_op_id(graph_ready_context)
    except ValidationError as exc:
        if strict_mode:
            raise
        _record_invalid_context(
            exc,
            attempts=attempts,
            base_strategy=base_strategy,
            dispatch_rule_cfg=dispatch_rule_cfg,
            search_report_state=search_report_state,
        )
        return None


def _record_invalid_context(
    exc: ValidationError,
    *,
    attempts: List[Dict[str, Any]],
    base_strategy: SortStrategy,
    dispatch_rule_cfg: str,
    search_report_state: Optional[OptimizationSearchReportState],
) -> None:
    reason = reason_from_validation(exc)
    record_rejected_attempt(
        attempts=attempts,
        strategy=base_strategy,
        dispatch_rule=dispatch_rule_cfg,
        reason=reason,
        message=str(exc),
    )
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(GRAPH_READY_PHASE, reason)
        search_report_state.mark_candidate_rejected(reason=reason)


def _update_graph_ready_profile(
    search_report_state: Optional[OptimizationSearchReportState],
    *,
    max_weight_profiles: int,
) -> None:
    if search_report_state is not None:
        search_report_state.update_candidate_profile(
            graph_ready_optimization=graph_ready_weight_profile_summary(max_weight_profiles=max_weight_profiles)
        )


def _run_weight_profiles(
    *,
    profiles: List[GraphReadyWeightProfile],
    best: Optional[Dict[str, Any]],
    version: int,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    graph_ready_context: Any,
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    clock: Callable[[], float],
    schedule_fn: Callable[..., Any],
    search_report_state: Optional[OptimizationSearchReportState],
    order: List[str],
) -> Optional[Dict[str, Any]]:
    for profile in profiles:
        if _deadline_reached(clock=clock, deadline=deadline, search_report_state=search_report_state):
            break
        candidate = _evaluate_profile(
            profile=profile,
            graph_ready_context=graph_ready_context,
            metrics_by_op_id=metrics_by_op_id,
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            base_strategy=base_strategy,
            base_params=base_params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=order,
            seed_sr_list=seed_sr_list,
            dispatch_rule_cfg=dispatch_rule_cfg,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            version=int(version),
            runtime_ms=max(int((clock() - t_begin) * 1000), 0),
            attempts=attempts,
            search_report_state=search_report_state,
        )
        if candidate is None:
            continue
        if not _candidate_should_replace_best(candidate, profile=profile, best=best, attempts=attempts, search_report_state=search_report_state):
            continue
        _accept_candidate(candidate, profile=profile, search_report_state=search_report_state)
        append_graph_trace(improvement_trace=improvement_trace, candidate=candidate, profile=profile, clock=clock, t_begin=t_begin)
        best = candidate
    return best


def _deadline_reached(
    *,
    clock: Callable[[], float],
    deadline: float,
    search_report_state: Optional[OptimizationSearchReportState],
) -> bool:
    if clock() <= deadline:
        return False
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()
        search_report_state.mark_phase_skipped(GRAPH_READY_PHASE, "time_budget")
    return True


def _evaluate_profile(
    *,
    profile: GraphReadyWeightProfile,
    graph_ready_context: Any,
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    order: List[str],
    seed_sr_list: List[ScheduleResult],
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    version: int,
    runtime_ms: int,
    attempts: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate_graph_ready_candidate(
            profile=profile,
            graph_ready_context=graph_ready_context,
            metrics_by_op_id=metrics_by_op_id,
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=base_strategy,
            params=base_params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=order,
            seed_sr_list=seed_sr_list,
            dispatch_rule=dispatch_rule_cfg,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            version=int(version),
            runtime_ms=int(runtime_ms),
        )
    except ValidationError as exc:
        if strict_mode:
            raise
        _record_profile_rejection(
            exc,
            profile=profile,
            attempts=attempts,
            base_strategy=base_strategy,
            dispatch_rule_cfg=dispatch_rule_cfg,
            search_report_state=search_report_state,
        )
        return None


def _record_profile_rejection(
    exc: ValidationError,
    *,
    profile: GraphReadyWeightProfile,
    attempts: List[Dict[str, Any]],
    base_strategy: SortStrategy,
    dispatch_rule_cfg: str,
    search_report_state: Optional[OptimizationSearchReportState],
) -> None:
    reason = reason_from_validation(exc)
    record_rejected_attempt(
        attempts=attempts,
        strategy=base_strategy,
        dispatch_rule=dispatch_rule_cfg,
        reason=reason,
        message=str(exc),
        profile_slug=profile.slug,
    )
    if search_report_state is not None:
        search_report_state.mark_candidate_rejected(reason=reason)


def _candidate_should_replace_best(
    candidate: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    best: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
) -> bool:
    fingerprint = None
    if search_report_state is not None:
        fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin=profile.candidate_origin)
    append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile)
    if fingerprint is not None and (fingerprint.same_as_parent or fingerprint.same_as_seen):
        return False
    return candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=profile.candidate_origin,
        incumbent_origin=_incumbent_origin(best, search_report_state),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=bool(search_report_state and search_report_state.best_fingerprint_changed()),
    )


def _incumbent_origin(
    best: Optional[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
) -> str:
    if search_report_state is not None:
        return str(search_report_state.best_origin or "baseline")
    return str((best or {}).get("candidate_origin") or "baseline")


def _accept_candidate(
    candidate: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    search_report_state: Optional[OptimizationSearchReportState],
) -> None:
    if search_report_state is not None:
        search_report_state.mark_candidate_accepted(candidate, origin=profile.candidate_origin)


def _candidate_order(
    best: Optional[Dict[str, Any]],
    *,
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
) -> List[str]:
    order = list((best or {}).get("order") or [])
    if order:
        return order
    return list(build_order(base_strategy, base_params or {}))


__all__ = [
    "GRAPH_READY_BASE_ORIGIN",
    "GRAPH_READY_DEFAULT_WEIGHT_PROFILES",
    "GRAPH_READY_LOCAL_SEARCH_ORIGIN",
    "GRAPH_READY_PHASE",
    "GRAPH_READY_REQUIRED_CONTEXT_FIELDS",
    "GRAPH_READY_WEIGHT_GRID_ORIGIN",
    "graph_ready_weight_profile_summary",
    "run_graph_ready_candidates",
]
