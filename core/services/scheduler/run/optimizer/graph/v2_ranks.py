"""GraphReady v2 rank features: common rank caches, rank-normalized metrics and the graph bonus."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Dict, Tuple

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BASELINE_RANK_PREFIX,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile

from .context import bool_metric, non_negative_number, required_non_negative_number
from .v2_keys import required_finite_metric, required_non_negative_metric, required_positive_metric

V2_COMMON_RANK_FIELDS = (
    ("due_deadline_hours", lambda metric: required_finite_metric(metric, "due_deadline_hours")),
    ("due_budget_hours", lambda metric: required_finite_metric(metric, "due_budget_hours")),
    ("due_pressure", lambda metric: required_non_negative_metric(required_finite_metric(metric, "due_pressure"), "due_pressure")),
    ("slack_hours", lambda metric: required_finite_metric(metric, "slack_hours")),
    ("remaining_due_burden_hours", lambda metric: required_positive_metric(metric, "remaining_due_burden_hours")),
    ("saveability", lambda metric: required_non_negative_metric(required_finite_metric(metric, "saveability"), "saveability")),
    ("processing_time_rank", lambda metric: required_non_negative_metric(required_finite_metric(metric, "processing_time_rank"), "processing_time_rank")),
    ("sacrifice_penalty", lambda metric: required_non_negative_metric(required_finite_metric(metric, "sacrifice_penalty"), "sacrifice_penalty")),
    ("critical_ratio", lambda metric: required_finite_metric(metric, "critical_ratio")),
    ("bottleneck_due_gate", lambda metric: required_non_negative_metric(required_finite_metric(metric, "bottleneck_due_gate"), "bottleneck_due_gate")),
    ("weighted_processing_hours", lambda metric: required_non_negative_metric(required_finite_metric(metric, "weighted_processing_hours"), "weighted_processing_hours")),
    ("weighted_due_pressure", lambda metric: required_non_negative_metric(required_finite_metric(metric, "weighted_due_pressure"), "weighted_due_pressure")),
    ("changeover_family_rank", lambda metric: required_non_negative_metric(required_finite_metric(metric, "changeover_family_rank"), "changeover_family_rank")),
)
_BASIS_INVARIANT_RANK_FIELDS = frozenset({
    "due_deadline_hours_rank01",
    "processing_time_rank_rank01",
    "weighted_processing_hours_rank01",
    "changeover_family_rank_rank01",
})


def metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
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


def v2_metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    try:
        return metric_bonus(metric, weights=weights)
    except ValidationError as exc:
        raise ValidationError(exc.message, field="graph_ready_v2_features", details=_v2_feature_details(exc)) from exc


def _v2_feature_details(exc: ValidationError) -> Dict[str, Any]:
    details = dict(exc.details or {})
    details["reason"] = "graph_ready_bad_v2_feature"
    return details


def normalized_v2_metrics_by_op_id(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    profile: GraphReadyWeightProfile,
    v2_common_rank_cache: Dict[str, Dict[int, float]],
    normalized_metrics_cache: Dict[Tuple[str, int], Dict[int, Dict[str, Any]]],
) -> Dict[int, Dict[str, Any]]:
    """Rank-normalized metrics for one basis and jitter seed, built once into the owner's cache."""
    if not metrics_by_op_id:
        return {}
    cache_key = (profile.feature_basis, int(profile.jitter_seed))
    base = normalized_metrics_cache.get(cache_key)
    if base is None:
        base = {int(op_id): dict(metric) for op_id, metric in metrics_by_op_id.items()}
        _attach_common_rank_cache(base, v2_common_rank_cache)
        jitter_by_op_id = _jitter_by_op_id(tuple(base), int(profile.jitter_seed))
        for op_id, metric in base.items():
            metric["graph_ready_v2_jitter"] = jitter_by_op_id[op_id]
        normalized_metrics_cache[cache_key] = base
    if profile.formula_slug != "graph_due_hybrid":
        return base
    out = {op_id: dict(metric) for op_id, metric in base.items()}
    _attach_rank01(
        out,
        field="graph_bonus",
        value_getter=lambda metric: v2_metric_bonus(metric, weights=profile.effective_weights),
    )
    return out


def build_v2_common_rank_cache(metrics_by_op_id: Dict[int, Dict[str, Any]]) -> Dict[str, Dict[int, float]]:
    metrics = {int(op_id): metric for op_id, metric in metrics_by_op_id.items()}
    cache: Dict[str, Dict[int, float]] = {}
    for field, value_getter in V2_COMMON_RANK_FIELDS:
        values = {op_id: float(value_getter(metric)) for op_id, metric in metrics.items()}
        cache[field + "_rank01"] = _rank01_by_op_id(values)
    if metrics and all(BASELINE_ORDERING_FIELD in row for row in metrics.values()):
        baseline = {op_id: row[BASELINE_ORDERING_FIELD] for op_id, row in metrics.items()}
        for field, value_getter in V2_COMMON_RANK_FIELDS:
            rank_field = field + "_rank01"
            if rank_field in _BASIS_INVARIANT_RANK_FIELDS:
                cache[BASELINE_RANK_PREFIX + rank_field] = cache[rank_field]
            else:
                values = {op_id: float(value_getter(metric)) for op_id, metric in baseline.items()}
                cache[BASELINE_RANK_PREFIX + rank_field] = _rank01_by_op_id(values)
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


@lru_cache(maxsize=32)
def _jitter_by_op_id(op_ids: Tuple[int, ...], seed: int) -> Dict[int, float]:
    return {op_id: _seeded_jitter(op_id=op_id, seed=seed) for op_id in op_ids}


def _seeded_jitter(*, op_id: int, seed: int) -> float:
    # 确定性整数散列(非随机):0x9E3779B1 为 32 位黄金比常数、0x45D9F3B 为整数 hash 混合常数,
    # 经异或+右移雪崩后取模归一到 [0,1),保证同 (op_id, seed) 可复现、不同 seed 产生可追踪的候选扰动。
    mixed = (int(op_id) * 0x45D9F3B) ^ ((int(seed) + 1) * 0x9E3779B1)
    mixed ^= mixed >> 16
    mixed = (mixed * 0x45D9F3B) & 0xFFFFFFFF
    mixed ^= mixed >> 16
    return float(mixed % 1000000) / 1000000.0


__all__ = [
    "V2_COMMON_RANK_FIELDS",
    "build_v2_common_rank_cache",
    "metric_bonus",
    "normalized_v2_metrics_by_op_id",
    "v2_metric_bonus",
]
