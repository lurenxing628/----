from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_graph_ready_context import (
    bool_metric,
    non_negative_number,
    optional_non_negative_number,
    required_non_negative_number,
)
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile, profile_payload
from .optimizer_graph_ready_reporting import public_params


def evaluate_graph_ready_candidate(
    *,
    profile: GraphReadyWeightProfile,
    graph_ready_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]],
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
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    version: int,
    runtime_ms: int,
) -> Dict[str, Any]:
    candidate_context = context_for_profile(
        graph_ready_context=graph_ready_context,
        metrics_by_op_id=metrics_by_op_id,
        profile=profile,
    )
    res, summ, used_strat, used_params = schedule_fn(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=strategy,
        strategy_params=_candidate_params(params, profile=profile, version=version),
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        batch_order_override=list(order),
        seed_results=seed_sr_list,
        dispatch_mode="sgs",
        dispatch_rule=dispatch_rule,
        resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_ready_context=candidate_context,
    )
    metrics = compute_metrics(res, batches)
    return _candidate_payload(
        res=res,
        summ=summ,
        used_strat=used_strat,
        used_params=used_params,
        metrics=metrics,
        profile=profile,
        order=order,
        dispatch_rule=dispatch_rule,
        objective_name=objective_name,
        scheduler=scheduler,
        optimizer_algo_stats=optimizer_algo_stats,
        resource_pool=resource_pool,
        seed_sr_list=seed_sr_list,
        version=version,
        runtime_ms=runtime_ms,
    )


def context_for_profile(
    *,
    graph_ready_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    profile: GraphReadyWeightProfile,
) -> Dict[str, Any]:
    context = dict(graph_ready_context)
    context["score_enabled"] = True
    context["graph_priority_key_by_op_id"] = {
        op_id: priority_key_for_metric(metric, profile=profile)
        for op_id, metric in sorted(metrics_by_op_id.items())
    }
    context["graph_ready_optimization_profile"] = profile_payload(profile, version=None)
    return context


def priority_key_for_metric(metric: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> Tuple[float, ...]:
    weights = profile.effective_weights
    rank = optional_non_negative_number(metric.get("critical_path_rank"), field="critical_path_rank")
    bonus = _metric_bonus(metric, weights=weights)
    return (
        float(round(-bonus, 6)),
        float(rank if rank is not None else 1_000_000_000.0),
    )


def _metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    return (
        _critical_path_bonus(metric, weights=weights)
        + _weighted_metric(metric, source="impact_count", weight="successor_count", weights=weights)
        + _downstream_work_bonus(metric, weights=weights)
        + _weighted_metric(metric, source="bottleneck_machine_score", weight="bottleneck_machine", weights=weights)
    )


def _critical_path_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    return float(weights["critical_path"] if bool_metric(metric, "is_on_critical_path") else 0.0)


def _downstream_work_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    hours = non_negative_number(metric.get("downstream_critical_minutes"), field="downstream_critical_minutes") / 60.0
    return float(hours * weights["downstream_work_hours"])


def _weighted_metric(metric: Dict[str, Any], *, source: str, weight: str, weights: Dict[str, float]) -> float:
    value = required_non_negative_number(metric, field=source)
    return float(value * weights[weight])


def _candidate_params(params: Dict[str, Any], *, profile: GraphReadyWeightProfile, version: int) -> Dict[str, Any]:
    candidate_params = dict(params or {})
    candidate_params["graph_ready_profile"] = profile_payload(profile, version=version)
    return candidate_params


def _candidate_payload(**kwargs: Any) -> Dict[str, Any]:
    profile = kwargs["profile"]
    metrics = kwargs["metrics"]
    return {
        "results": kwargs["res"],
        "summary": kwargs["summ"],
        "strategy": kwargs["used_strat"],
        "params": public_params(kwargs["used_params"]),
        "dispatch_mode": "sgs",
        "dispatch_rule": str(kwargs["dispatch_rule"] or ""),
        "order": list(kwargs["order"]),
        "metrics": metrics,
        "score": (float(kwargs["summ"].failed_ops),) + objective_score(kwargs["objective_name"], metrics),
        "algo_stats": merge_algo_stats(kwargs["optimizer_algo_stats"], snapshot_algo_stats(kwargs["scheduler"])),
        "resource_pool": kwargs["resource_pool"] or {},
        "seed_result_count": len(kwargs["seed_sr_list"] or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(kwargs["seed_sr_list"] or [])],
        "mutable_scope": _mutable_scope(profile, version=int(kwargs["version"])),
        "candidate_origin": profile.candidate_origin,
        "runtime_ms": int(kwargs["runtime_ms"]),
        "graph_ready_profile": profile_payload(profile, version=int(kwargs["version"])),
    }


def _mutable_scope(profile: GraphReadyWeightProfile, *, version: int) -> Dict[str, Any]:
    return {
        "scope": "graph_ready_priority",
        "weight_profile_slug": profile.slug,
        "raw_weights": dict(profile.raw_weights),
        "candidate_policy": profile.candidate_policy,
        "seed": int(version),
    }
