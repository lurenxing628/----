from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats
from core.infrastructure.errors import ValidationError

from .optimizer_attempt_records import validation_error_origin
from .optimizer_candidate_fingerprint import stable_fingerprint
from .optimizer_grasp_ig_specs import GRASP_ORIGIN, IG_ORIGIN, build_grasp_ig_candidate_specs
from .optimizer_search_state import append_unique_rejected_attempt

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


GRASP_IG_PHASE = "grasp_ig_candidate_construction"


def _safe_strategy_value(strategy: Any) -> str:
    return str(getattr(strategy, "value", strategy) or "")


def _public_candidate_params(params: Any) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    out = dict(params)
    out.pop("candidate_construction", None)
    return out


def _candidate_tag(origin: str, index: int, dispatch_mode: str, dispatch_rule: str) -> str:
    return f"{origin}:r{int(index)}|{dispatch_mode}:{dispatch_rule}"


def _evaluate_candidate(
    *,
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    order: List[str],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode: str,
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    construction: Dict[str, Any],
) -> Dict[str, Any]:
    candidate_params = dict(params or {})
    candidate_params["candidate_construction"] = dict(construction or {})
    res, summ, used_strat, used_params = schedule_fn(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=strategy,
        strategy_params=candidate_params,
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        batch_order_override=list(order),
        seed_results=seed_sr_list,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_ready_context=graph_ready_context,
    )
    metrics = compute_metrics(res, batches)
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": _public_candidate_params(used_params),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": list(order),
        "metrics": metrics,
        "score": (float(summ.failed_ops),) + objective_score(objective_name, metrics),
        "algo_stats": algo_stats,
        "resource_pool": resource_pool or {},
        "seed_result_count": len(seed_sr_list or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(seed_sr_list or [])],
        "mutable_scope": {
            "scope": "candidate_construction_batch_order",
            "batch_count": len(order or []),
            "candidate_source": str(construction.get("family") or ""),
            "restart_index": int(construction.get("restart_index") or 0),
        },
    }


def _append_attempt(*, attempts: List[Dict[str, Any]], candidate: Dict[str, Any], origin: str, index: int) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    attempts.append(
        {
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": _safe_strategy_value(candidate.get("strategy")),
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "used_params": dict(candidate.get("params") or {}),
            "score": list(candidate.get("score") or []),
            "failed_ops": int(getattr(candidate.get("summary"), "failed_ops", 0) or 0),
            "metrics": metrics.to_dict(),
            "algo_stats": candidate.get("algo_stats") or {},
        }
    )


def _append_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    origin: str,
    index: int,
    now: Callable[[], float],
    t_begin: float,
) -> None:
    if len(improvement_trace) >= 200:
        return
    metrics = candidate["metrics"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    improvement_trace.append(
        {
            "elapsed_ms": int((now() - t_begin) * 1000),
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": _safe_strategy_value(candidate.get("strategy")),
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(candidate.get("score") or []),
            "metrics": metrics.to_dict(),
        }
    )


def _append_rejected_attempt(
    *,
    attempts: List[Dict[str, Any]],
    origin: str,
    index: int,
    strategy: SortStrategy,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> None:
    append_unique_rejected_attempt(
        attempts,
        {
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": strategy.value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "source": "candidate_rejected",
            "origin": validation_error_origin(exc),
        },
    )


def _record_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    origin: str,
    index: int,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    now: Callable[[], float],
    t_begin: float,
) -> Optional[Dict[str, Any]]:
    if search_report_state is not None:
        search_report_state.mark_candidate_evaluated(candidate, origin=origin)
    _append_attempt(attempts=attempts, candidate=candidate, origin=origin, index=index)
    if best is not None and candidate["score"] >= best["score"]:
        return best
    if search_report_state is not None:
        search_report_state.mark_candidate_accepted(candidate, origin=origin)
    _append_trace(
        improvement_trace=improvement_trace,
        candidate=candidate,
        origin=origin,
        index=index,
        now=now,
        t_begin=t_begin,
    )
    return candidate


def _mark_phase_skipped(
    search_report_state: Optional[OptimizationSearchReportState],
    reason: str,
    **extra: Any,
) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(GRASP_IG_PHASE, reason, **extra)


def _deadline_reached(now: Callable[[], float], deadline: float, search_report_state: Optional[OptimizationSearchReportState]) -> bool:
    if now() <= deadline:
        return False
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()
    return True


def _candidate_specs_for_run(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    version: int,
    candidate_construction: Dict[str, Any],
    dispatch_rule_cfg: str,
    valid_dispatch_rules: List[str],
    batch_order_enabled: bool,
    rng_factory: Callable[[int], Any],
    search_report_state: Optional[OptimizationSearchReportState],
) -> Optional[List[Dict[str, Any]]]:
    if str(algo_mode or "").strip().lower() != "improve":
        _mark_phase_skipped(search_report_state, "algo_mode_not_improve")
        return None
    if not bool(batch_order_enabled):
        _mark_phase_skipped(search_report_state, "batch_order_dispatch_unavailable")
        return None

    base_order = list(build_order(base_strategy, base_params or {}))
    if len(base_order) < 2:
        _mark_phase_skipped(search_report_state, "order_too_short", order_length=len(base_order))
        return None

    parent_order = list((best or {}).get("order") or base_order)
    specs = build_grasp_ig_candidate_specs(
        base_order=base_order,
        parent_order=parent_order,
        version=int(version),
        candidate_construction=candidate_construction if isinstance(candidate_construction, dict) else {},
        dispatch_rule_cfg=dispatch_rule_cfg,
        valid_dispatch_rules=valid_dispatch_rules,
        rng_factory=rng_factory,
    )
    if not specs:
        _mark_phase_skipped(search_report_state, "candidate_budget_empty")
        return None
    for spec in specs:
        spec["dispatch_mode"] = "batch_order"
    return _dedupe_candidate_specs(specs)


def _dedupe_candidate_specs(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for spec in list(specs or []):
        fingerprint = _spec_decision_fingerprint(spec)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(spec)
    return out


def _spec_decision_fingerprint(spec: Dict[str, Any]) -> str:
    return stable_fingerprint(
        {
            "schema_version": 1,
            "fingerprint_scope": "candidate_spec_decision",
            "dispatch_mode": str(spec.get("dispatch_mode") or "batch_order"),
            "dispatch_rule": str(spec.get("dispatch_rule") or ""),
            "batch_order": list(spec.get("order") or []),
        }
    )


def _run_candidate_spec(
    *,
    spec: Dict[str, Any],
    best: Optional[Dict[str, Any]],
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    clock: Callable[[], float],
    t_begin: float,
) -> Optional[Dict[str, Any]]:
    origin = str(spec["origin"])
    index = int(spec["restart_index"])
    dispatch_mode = str(spec.get("dispatch_mode") or "batch_order")
    dispatch_rule = str(spec["dispatch_rule"])
    try:
        candidate = _evaluate_candidate(
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=base_strategy,
            params=dict(base_params or {}),
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=list(spec["order"]),
            seed_sr_list=seed_sr_list,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
            construction=dict(spec["construction"]),
        )
    except ValidationError as exc:
        if bool(strict_mode):
            raise
        _append_rejected_attempt(
            attempts=attempts,
            origin=origin,
            index=index,
            strategy=base_strategy,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error")
        return best
    return _record_candidate(
        best=best,
        candidate=candidate,
        origin=origin,
        index=index,
        attempts=attempts,
        improvement_trace=improvement_trace,
        search_report_state=search_report_state,
        now=clock,
        t_begin=t_begin,
    )


def run_grasp_ig_candidates(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    candidate_construction: Dict[str, Any],
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
    valid_dispatch_rules: List[str],
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
    rng_factory: Callable[[int], Any],
    schedule_fn: Callable[..., Any],
    batch_order_enabled: bool = True,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Optional[Dict[str, Any]]:
    if graph_ready_context is not None:
        _mark_phase_skipped(search_report_state, "graph_ready_requires_graph_neighborhood")
        return best
    specs = _candidate_specs_for_run(
        algo_mode=algo_mode,
        best=best,
        base_strategy=base_strategy,
        base_params=base_params,
        build_order=build_order,
        version=int(version),
        candidate_construction=candidate_construction,
        dispatch_rule_cfg=dispatch_rule_cfg,
        valid_dispatch_rules=valid_dispatch_rules,
        batch_order_enabled=batch_order_enabled,
        rng_factory=rng_factory,
        search_report_state=search_report_state,
    )
    if specs is None:
        return best

    for spec in specs:
        if _deadline_reached(clock, deadline, search_report_state):
            break
        best = _run_candidate_spec(
            spec=spec,
            best=best,
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            base_strategy=base_strategy,
            base_params=base_params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            seed_sr_list=seed_sr_list,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
            attempts=attempts,
            improvement_trace=improvement_trace,
            search_report_state=search_report_state,
            clock=clock,
            t_begin=t_begin,
        )
    return best


__all__ = [
    "GRASP_IG_PHASE",
    "GRASP_ORIGIN",
    "IG_ORIGIN",
    "run_grasp_ig_candidates",
]
