from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats
from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_context import (
    bool_metric,
    non_negative_number,
    optional_non_negative_number,
    required_non_negative_number,
)
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile, finite_number, profile_payload
from .optimizer_graph_ready_reporting import public_params

GRAPH_READY_V2_NORMALIZATION_VERSION = "rank_percentile_v1"


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
    metrics_for_profile = _metrics_for_profile(metrics_by_op_id, profile=profile)
    context["graph_priority_key_by_op_id"] = {
        op_id: priority_key_for_metric(metric, profile=profile)
        for op_id, metric in sorted(metrics_for_profile.items())
    }
    context["graph_ready_optimization_profile"] = profile_payload(profile, version=None)
    if _uses_v2_formula(profile):
        context["graph_ready_v2_normalization_version"] = GRAPH_READY_V2_NORMALIZATION_VERSION
    return context


def priority_key_for_metric(metric: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> Tuple[float, ...]:
    if _uses_v2_formula(profile):
        return _v2_priority_key_for_metric(metric, profile=profile)
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


def _metrics_for_profile(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    profile: GraphReadyWeightProfile,
) -> Dict[int, Dict[str, Any]]:
    if not _uses_v2_formula(profile):
        return {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
    return _normalized_v2_metrics_by_op_id(metrics_by_op_id, profile=profile)


def _uses_v2_formula(profile: GraphReadyWeightProfile) -> bool:
    return str(profile.formula_version).startswith("graph_ready_v2")


def _normalized_v2_metrics_by_op_id(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    profile: GraphReadyWeightProfile,
) -> Dict[int, Dict[str, Any]]:
    out = {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
    _attach_rank01(out, field="due_deadline_hours", value_getter=lambda metric: _required_finite_metric(metric, "due_deadline_hours"))
    _attach_rank01(out, field="due_pressure", value_getter=lambda metric: _required_non_negative_metric(metric, "due_pressure"))
    _attach_rank01(out, field="slack_hours", value_getter=lambda metric: _required_finite_metric(metric, "slack_hours"))
    _attach_rank01(out, field="remaining_work_hours", value_getter=lambda metric: _required_positive_metric(metric, "remaining_work_hours"))
    _attach_rank01(out, field="saveability", value_getter=lambda metric: _required_non_negative_metric(metric, "saveability"))
    _attach_rank01(out, field="processing_time_rank", value_getter=lambda metric: _required_non_negative_metric(metric, "processing_time_rank"))
    _attach_rank01(out, field="sacrifice_penalty", value_getter=lambda metric: _required_non_negative_metric(metric, "sacrifice_penalty"))
    _attach_rank01(out, field="critical_ratio", value_getter=lambda metric: _required_finite_metric(metric, "critical_ratio"))
    _attach_rank01(out, field="bottleneck_due_gate", value_getter=lambda metric: _required_non_negative_metric(metric, "bottleneck_due_gate"))
    _attach_rank01(out, field="graph_bonus", value_getter=lambda metric: _metric_bonus(metric, weights=profile.effective_weights))
    for op_id, metric in out.items():
        metric["graph_ready_v2_jitter"] = _seeded_jitter(op_id=op_id, seed=int(profile.jitter_seed))
        metric["graph_ready_v2_normalization_version"] = GRAPH_READY_V2_NORMALIZATION_VERSION
    return out


def _attach_rank01(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    field: str,
    value_getter: Callable[[Dict[str, Any]], float],
) -> None:
    values = {op_id: float(value_getter(metric)) for op_id, metric in metrics_by_op_id.items()}
    for op_id, rank in _rank01_by_op_id(values).items():
        metrics_by_op_id[op_id][field + "_rank01"] = float(rank)


def _rank01_by_op_id(values_by_op_id: Dict[int, float]) -> Dict[int, float]:
    if not values_by_op_id:
        return {}
    ordered = sorted(values_by_op_id.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 0.0}
    ranks: Dict[int, float] = {}
    denominator = float(len(ordered) - 1)
    index = 0
    while index < len(ordered):
        value = ordered[index][1]
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == value:
            end += 1
        average_rank = ((index + end) / 2.0) / denominator
        for pos in range(index, end + 1):
            ranks[ordered[pos][0]] = float(average_rank)
        index = end + 1
    return ranks


def _seeded_jitter(*, op_id: int, seed: int) -> float:
    # 确定性整数散列(非随机):0x9E3779B1 为 32 位黄金比常数、0x45D9F3B 为整数 hash 混合常数,
    # 经异或+右移雪崩后取模归一到 [0,1),保证同 (op_id, seed) 可复现、不同 seed 产生可追踪的候选扰动。
    mixed = (int(op_id) * 0x45D9F3B) ^ ((int(seed) + 1) * 0x9E3779B1)
    mixed ^= mixed >> 16
    mixed = (mixed * 0x45D9F3B) & 0xFFFFFFFF
    mixed ^= mixed >> 16
    return float(mixed % 1000000) / 1000000.0


def _v2_priority_key_for_metric(metric: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> Tuple[float, ...]:
    formula = str(profile.formula_slug or "").strip()
    due_deadline = _required_non_negative_metric(metric, "due_deadline_hours_rank01")
    due_pressure = _required_non_negative_metric(metric, "due_pressure_rank01")
    slack_hours = _required_non_negative_metric(metric, "slack_hours_rank01")
    remaining = _required_non_negative_metric(metric, "remaining_work_hours_rank01")
    saveability = _required_non_negative_metric(metric, "saveability_rank01")
    processing_rank = _required_non_negative_metric(metric, "processing_time_rank_rank01")
    sacrifice_penalty = _required_non_negative_metric(metric, "sacrifice_penalty_rank01")
    critical_ratio = _required_non_negative_metric(metric, "critical_ratio_rank01")
    bottleneck_due_gate = _required_non_negative_metric(metric, "bottleneck_due_gate_rank01")
    graph_bonus = _required_non_negative_metric(metric, "graph_bonus_rank01")
    jitter = _stable_jitter(metric)

    if formula == "edd":
        return (due_deadline, sacrifice_penalty, processing_rank, jitter)
    if formula == "spt":
        return (processing_rank, due_deadline, sacrifice_penalty, jitter)
    if formula == "min_slack":
        return (slack_hours, sacrifice_penalty, processing_rank, jitter)
    if formula == "critical_ratio":
        return (critical_ratio, sacrifice_penalty, processing_rank, jitter)
    if formula == "atc_like":
        return (sacrifice_penalty, -due_pressure, -saveability, processing_rank, jitter)
    if formula == "saveability":
        return (sacrifice_penalty, -due_pressure, -saveability, remaining, processing_rank, jitter)
    if formula == "sacrifice_long":
        return (sacrifice_penalty, -saveability, remaining, processing_rank, jitter)
    if formula == "graph_due_hybrid":
        return (sacrifice_penalty, -due_pressure, -graph_bonus, processing_rank, jitter)
    if formula == "bottleneck_due_gated":
        return (sacrifice_penalty, -due_pressure, -bottleneck_due_gate, processing_rank, jitter)
    if formula == "micro_perturbation":
        # 小扰动只在两个主交期目标(牺牲度、交期压力)都相同的候选间用 jitter 打破平局(压过次要的工时排名),
        # 不跨交期分数差异重排,符合"只在分数接近的 ready 候选之间做";同分时不同 seed 产生不同候选以提供多样性。
        return (sacrifice_penalty, -due_pressure, jitter, processing_rank)
    raise ValidationError(
        f"GraphReady v2 不支持候选公式：{formula}",
        field="graph_ready_v2_formula",
        details={"reason": "graph_ready_bad_v2_formula"},
    )


def _required_finite_metric(metric: Dict[str, Any], field: str) -> float:
    if field not in metric:
        raise ValidationError(
            f"GraphReady v2 图指标缺少 {field}。",
            field="graph_ready_context",
            details={"reason": "graph_ready_missing_v2_feature"},
        )
    return float(finite_number(metric.get(field), field=field, reason="graph_ready_bad_v2_feature"))


def _required_non_negative_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_finite_metric(metric, field)
    if number < 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须是非负数。",
            field="graph_ready_context",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _required_positive_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_non_negative_metric(metric, field)
    if number <= 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须大于 0。",
            field="graph_ready_context",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _stable_jitter(metric: Dict[str, Any]) -> float:
    return _required_non_negative_metric(metric, "graph_ready_v2_jitter")


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
