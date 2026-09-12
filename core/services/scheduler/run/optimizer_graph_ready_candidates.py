from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics
from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_candidate_payload import build_graph_ready_candidate_payload
from .optimizer_graph_ready_context import (
    bool_metric,
    non_negative_number,
    optional_non_negative_number,
    required_non_negative_number,
)
from .optimizer_graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BASELINE_RANK_PREFIX,
    BATCH_WORKLOAD_BASIS,
    select_profile_metrics,
)
from .optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    GraphReadyWeightProfile,
    finite_number,
    profile_payload,
)
from .optimizer_graph_ready_repair_neighbors import repair_priority_context

GRAPH_READY_V2_NORMALIZATION_VERSION = "rank_percentile_v1"
_V2_COMMON_RANK_FIELDS = (
    ("due_deadline_hours", lambda metric: _required_finite_metric(metric, "due_deadline_hours")),
    ("due_budget_hours", lambda metric: _v2_due_budget_hours(metric)),
    ("due_pressure", lambda metric: _required_non_negative_metric(metric, "due_pressure")),
    ("slack_hours", lambda metric: _required_finite_metric(metric, "slack_hours")),
    ("remaining_work_hours", lambda metric: _required_positive_metric(metric, "remaining_work_hours")),
    ("remaining_due_burden_hours", lambda metric: _v2_remaining_due_burden_hours(metric)),
    ("saveability", lambda metric: _required_non_negative_metric(metric, "saveability")),
    ("processing_time_rank", lambda metric: _required_non_negative_metric(metric, "processing_time_rank")),
    ("sacrifice_penalty", lambda metric: _required_non_negative_metric(metric, "sacrifice_penalty")),
    ("critical_ratio", lambda metric: _required_finite_metric(metric, "critical_ratio")),
    ("bottleneck_due_gate", lambda metric: _required_non_negative_metric(metric, "bottleneck_due_gate")),
)


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
    clock: Callable[[], float],
    v2_common_rank_cache: Optional[Dict[str, Dict[int, float]]] = None,
    repair_order: Optional[List[str]] = None,
    repair_decision: Optional[Any] = None,
    before_decode: Optional[Callable[[], None]] = None,
    inspect_decision: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    # runtime_ms 合同语义是"该候选自身的构造+解码+评估耗时"(同分 tie-break 偏好更快候选,
    # 见 optimizer_candidate_comparison.candidate_runtime_ms 与 GRAPH_READY_SELECTION_TIEBREAKER)。
    # 必须在这里 per-candidate 计时,不能由调用方传"自优化开始的累计流逝时间"——
    # 累计值随 profile 评估序号单调递增,会把"偏好更快"悄悄变成"偏好更早评估的 profile"。
    t_candidate_begin = clock()
    if repair_decision is not None:
        decision_order = list(repair_decision.batch_order)
        if repair_order is not None and repair_order != decision_order:
            raise ValidationError("GraphReady 修补批序决策不一致。", field="graph_ready_elite_repair")
        repair_order = decision_order
    _validate_repair_decision(profile, order=order, repair_order=repair_order)
    candidate_context = context_for_profile(
        graph_ready_context=graph_ready_context,
        metrics_by_op_id=metrics_by_op_id,
        profile=profile,
        v2_common_rank_cache=v2_common_rank_cache,
    )
    candidate_operations = algo_ops_to_schedule
    if repair_decision is not None:
        from .optimizer_graph_ready_repair_decisions import apply_repair_decision

        candidate_context, candidate_operations = apply_repair_decision(
            candidate_context, algo_ops_to_schedule, repair_decision, resource_pool,
        )
    elif repair_order is not None:
        candidate_context = repair_priority_context(candidate_context, operations=algo_ops_to_schedule, order=repair_order)
    if inspect_decision is not None:
        inspect_decision(candidate_context)
    if before_decode is not None:
        before_decode()
    res, summ, used_strat, used_params = schedule_fn(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=candidate_operations,
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
    metrics = compute_metrics(
        res, batches, expected_operations=algo_ops_to_schedule, seed_results=seed_sr_list,
        failure_details=getattr(summ, "failure_details", ()),
    )
    return build_graph_ready_candidate_payload(
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
        runtime_ms=max(int((clock() - t_candidate_begin) * 1000), 0),
        repair_decision=repair_decision,
    )


def _validate_repair_decision(profile: GraphReadyWeightProfile, *, order: List[str], repair_order: Optional[List[str]]) -> None:
    repaired = profile.candidate_origin == GRAPH_READY_V2_REPAIRED_ORIGIN
    if repaired != (repair_order is not None) or (repaired and (profile.candidate_policy != "elite_repair" or order != repair_order)):
        raise ValidationError(
            "GraphReady 修补来源必须对应同一份显式优先决策。", field="graph_ready_elite_repair",
            details={"reason": "graph_ready_bad_repair_decision"},
        )


def context_for_profile(
    *,
    graph_ready_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    profile: GraphReadyWeightProfile,
    v2_common_rank_cache: Optional[Dict[str, Dict[int, float]]] = None,
) -> Dict[str, Any]:
    context = dict(graph_ready_context)
    context["score_enabled"] = True
    metrics_for_profile = _metrics_for_profile(
        metrics_by_op_id,
        profile=profile,
        v2_common_rank_cache=v2_common_rank_cache,
    )
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
    v2_common_rank_cache: Optional[Dict[str, Dict[int, float]]] = None,
) -> Dict[int, Dict[str, Any]]:
    if not _uses_v2_formula(profile):
        return {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
    selected = select_profile_metrics(metrics_by_op_id, profile=profile)
    if v2_common_rank_cache is not None:
        is_baseline = profile.feature_basis == BATCH_WORKLOAD_BASIS
        v2_common_rank_cache = {
            field[len(BASELINE_RANK_PREFIX):] if is_baseline else field: ranks
            for field, ranks in v2_common_rank_cache.items()
            if field.startswith(BASELINE_RANK_PREFIX) == is_baseline
        }
    return _normalized_v2_metrics_by_op_id(
        selected,
        profile=profile,
        v2_common_rank_cache=v2_common_rank_cache,
    )


def _uses_v2_formula(profile: GraphReadyWeightProfile) -> bool:
    return str(profile.formula_version).startswith("graph_ready_v2")


def _normalized_v2_metrics_by_op_id(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    profile: GraphReadyWeightProfile,
    v2_common_rank_cache: Optional[Dict[str, Dict[int, float]]] = None,
) -> Dict[int, Dict[str, Any]]:
    out = {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
    if v2_common_rank_cache is None:
        for field, value_getter in _V2_COMMON_RANK_FIELDS:
            _attach_rank01(out, field=field, value_getter=value_getter)
    else:
        _attach_common_rank_cache(out, v2_common_rank_cache)
    _attach_rank01(out, field="graph_bonus", value_getter=lambda metric: _v2_metric_bonus(metric, weights=profile.effective_weights))
    extra_fields = {
        "weighted_spt": ("weighted_processing_hours",),
        "weighted_atc": ("weighted_processing_hours", "weighted_due_pressure"),
        "type_group": ("changeover_family_rank",),
        "type_group_reverse": ("changeover_family_rank",),
    }.get(profile.formula_slug, ())
    for field in extra_fields:
        _attach_rank01(out, field=field, value_getter=lambda metric, field=field: _required_non_negative_metric(metric, field))
    for op_id, metric in out.items():
        metric["graph_ready_v2_jitter"] = _seeded_jitter(op_id=op_id, seed=int(profile.jitter_seed))
        metric["graph_ready_v2_normalization_version"] = GRAPH_READY_V2_NORMALIZATION_VERSION
    return out


def build_v2_common_rank_cache(metrics_by_op_id: Dict[int, Dict[str, Any]]) -> Dict[str, Dict[int, float]]:
    metrics = {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
    cache: Dict[str, Dict[int, float]] = {}
    for field, value_getter in _V2_COMMON_RANK_FIELDS:
        values = {op_id: float(value_getter(metric)) for op_id, metric in metrics.items()}
        cache[field + "_rank01"] = _rank01_by_op_id(values)
    if metrics and all(BASELINE_ORDERING_FIELD in row for row in metrics.values()):
        baseline = {op_id: row[BASELINE_ORDERING_FIELD] for op_id, row in metrics.items()}
        cache.update({BASELINE_RANK_PREFIX + field: ranks for field, ranks in build_v2_common_rank_cache(baseline).items()})
    return cache


def _attach_common_rank_cache(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    v2_common_rank_cache: Dict[str, Dict[int, float]],
) -> None:
    for rank_field, ranks_by_op_id in v2_common_rank_cache.items():
        for op_id in metrics_by_op_id:
            if op_id not in ranks_by_op_id:
                raise ValidationError(
                    f"GraphReady v2 图指标缺少 {rank_field} 缓存。",
                    field="graph_ready_v2_features",
                    details={"reason": "graph_ready_missing_v2_feature"},
                )
            metrics_by_op_id[op_id][rank_field] = float(ranks_by_op_id[op_id])


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
    due_budget = _required_non_negative_metric(metric, "due_budget_hours_rank01")
    due_pressure = _required_non_negative_metric(metric, "due_pressure_rank01")
    slack_hours = _required_non_negative_metric(metric, "slack_hours_rank01")
    remaining = _required_non_negative_metric(metric, "remaining_due_burden_hours_rank01")
    saveability = _required_non_negative_metric(metric, "saveability_rank01")
    processing_rank = _required_non_negative_metric(metric, "processing_time_rank_rank01")
    sacrifice_penalty = _required_non_negative_metric(metric, "sacrifice_penalty_rank01")
    critical_ratio = _required_non_negative_metric(metric, "critical_ratio_rank01")
    bottleneck_due_gate = _required_non_negative_metric(metric, "bottleneck_due_gate_rank01")
    graph_bonus = _required_non_negative_metric(metric, "graph_bonus_rank01")
    jitter = _stable_jitter(metric)

    objective_key = _objective_priority_key(metric, formula, due_deadline, slack_hours, processing_rank, jitter)
    if objective_key is not None:
        return objective_key
    if formula == "edd":
        return (due_deadline, sacrifice_penalty, processing_rank, jitter)
    if formula == "spt":
        return (processing_rank, due_budget, sacrifice_penalty, jitter)
    if formula == "min_slack":
        return (slack_hours, sacrifice_penalty, processing_rank, jitter)
    if formula == "critical_ratio":
        return (critical_ratio, sacrifice_penalty, processing_rank, jitter)
    if formula == "atc_like":
        return (-due_pressure, sacrifice_penalty, -saveability, processing_rank, jitter)
    if formula == "saveability":
        return (-saveability, sacrifice_penalty, -due_pressure, remaining, processing_rank, jitter)
    if formula == "sacrifice_long":
        return (sacrifice_penalty, remaining, -saveability, due_budget, processing_rank, jitter)
    if formula == "graph_due_hybrid":
        return (-graph_bonus, -due_pressure, sacrifice_penalty, processing_rank, jitter)
    if formula == "bottleneck_due_gated":
        return (-bottleneck_due_gate, sacrifice_penalty, -due_pressure, processing_rank, jitter)
    if formula == "micro_perturbation":
        # 小扰动只在两个主交期目标(牺牲度、交期压力)都相同的候选间用 jitter 打破平局(压过次要的工时排名),
        # 不跨交期分数差异重排,符合"只在分数接近的 ready 候选之间做";同分时不同 seed 产生不同候选以提供多样性。
        return (sacrifice_penalty, -due_pressure, jitter, processing_rank)
    raise ValidationError(
        f"GraphReady v2 不支持候选公式：{formula}",
        field="graph_ready_v2_formula",
        details={"reason": "graph_ready_bad_v2_formula"},
    )


def _objective_priority_key(metric, formula, due_deadline, slack_hours, processing_rank, jitter):
    if formula == "weighted_spt":
        return (_required_non_negative_metric(metric, "weighted_processing_hours_rank01"), due_deadline, slack_hours, jitter)
    if formula == "weighted_atc":
        return (-_required_non_negative_metric(metric, "weighted_due_pressure_rank01"),
                _required_non_negative_metric(metric, "weighted_processing_hours_rank01"), slack_hours, jitter)
    if formula in {"type_group", "type_group_reverse"}:
        family = _required_non_negative_metric(metric, "changeover_family_rank_rank01")
        return (family if formula == "type_group" else -family, due_deadline, processing_rank, jitter)
    return None


def _required_finite_metric(metric: Dict[str, Any], field: str) -> float:
    if field not in metric:
        raise ValidationError(
            f"GraphReady v2 图指标缺少 {field}。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_missing_v2_feature"},
        )
    try:
        return float(finite_number(metric.get(field), field=field, reason="graph_ready_bad_v2_feature"))
    except ValidationError as exc:
        raise ValidationError(exc.message, field="graph_ready_v2_features", details=exc.details) from exc


def _required_non_negative_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_finite_metric(metric, field)
    if number < 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须是非负数。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _v2_metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    try:
        return _metric_bonus(metric, weights=weights)
    except ValidationError as exc:
        raise ValidationError(exc.message, field="graph_ready_v2_features", details=_v2_feature_details(exc)) from exc


def _v2_feature_details(exc: ValidationError) -> Dict[str, Any]:
    details = dict(getattr(exc, "details", None) or {})
    details["reason"] = "graph_ready_bad_v2_feature"
    return details


def _required_positive_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_non_negative_metric(metric, field)
    if number <= 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须大于 0。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _v2_due_budget_hours(metric: Dict[str, Any]) -> float:
    return _required_finite_metric(metric, "due_budget_hours")


def _v2_remaining_due_burden_hours(metric: Dict[str, Any]) -> float:
    return _required_positive_metric(metric, "remaining_due_burden_hours")


def _stable_jitter(metric: Dict[str, Any]) -> float:
    return _required_non_negative_metric(metric, "graph_ready_v2_jitter")


def _candidate_params(params: Dict[str, Any], *, profile: GraphReadyWeightProfile, version: int) -> Dict[str, Any]:
    candidate_params = dict(params or {})
    candidate_params["graph_ready_profile"] = profile_payload(profile, version=version)
    return candidate_params
