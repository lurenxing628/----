"""GraphReady v2 rank features: common rank caches, rank-normalized metrics and the graph bonus."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Dict, Tuple

from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BASELINE_RANK_PREFIX,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile

V2_COMMON_RANK_FIELDS = (
    "due_deadline_hours",
    "due_budget_hours",
    "due_pressure",
    "slack_hours",
    "remaining_due_burden_hours",
    "saveability",
    "processing_time_rank",
    "sacrifice_penalty",
    "critical_ratio",
    "bottleneck_due_gate",
    "weighted_processing_hours",
    "weighted_due_pressure",
    "changeover_family_rank",
)
_BASIS_INVARIANT_RANK_FIELDS = frozenset({
    "due_deadline_hours_rank01",
    "processing_time_rank_rank01",
    "weighted_processing_hours_rank01",
    "changeover_family_rank_rank01",
})


def metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    return float(
        (weights["critical_path"] if metric.get("is_on_critical_path") else 0.0)
        + float(metric["impact_count"]) * weights["successor_count"]
        + (float(metric["downstream_critical_minutes"]) / 60.0) * weights["downstream_work_hours"]
        + float(metric["bottleneck_machine_score"]) * weights["bottleneck_machine"]
    )


def v2_metric_bonus(metric: Dict[str, Any], *, weights: Dict[str, float]) -> float:
    return metric_bonus(metric, weights=weights)


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
        value_getter=lambda metric: metric_bonus(metric, weights=profile.effective_weights),
    )
    return out


def build_v2_common_rank_cache(metrics_by_op_id: Dict[int, Dict[str, Any]]) -> Dict[str, Dict[int, float]]:
    metrics = {int(op_id): metric for op_id, metric in metrics_by_op_id.items()}
    cache: Dict[str, Dict[int, float]] = {}
    for field in V2_COMMON_RANK_FIELDS:
        values = {op_id: float(metric[field]) for op_id, metric in metrics.items()}
        cache[field + "_rank01"] = _rank01_by_op_id(values)
    if metrics and all(BASELINE_ORDERING_FIELD in row for row in metrics.values()):
        baseline = {op_id: row[BASELINE_ORDERING_FIELD] for op_id, row in metrics.items()}
        for field in V2_COMMON_RANK_FIELDS:
            rank_field = field + "_rank01"
            if rank_field in _BASIS_INVARIANT_RANK_FIELDS:
                cache[BASELINE_RANK_PREFIX + rank_field] = cache[rank_field]
            else:
                values = {op_id: float(metric[field]) for op_id, metric in baseline.items()}
                cache[BASELINE_RANK_PREFIX + rank_field] = _rank01_by_op_id(values)
    return cache


def _attach_common_rank_cache(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    v2_common_rank_cache: Dict[str, Dict[int, float]],
) -> None:
    for rank_field, ranks_by_op_id in v2_common_rank_cache.items():
        for op_id, metric in metrics_by_op_id.items():
            metric[rank_field] = float(ranks_by_op_id[op_id])


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
