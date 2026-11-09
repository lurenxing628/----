from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.graph.scoring import graph_score_components

from .schedule_graph_dispatch_context import GRAPH_CYCLE_DISABLED_REASON

GRAPH_SCORE_WEIGHTS_ZERO_REASON = "score_weights_zero"
_GRAPH_SCORE_SAMPLE_LIMIT = 10


def graph_score_weights(cfg: ScheduleConfigSnapshot) -> Dict[str, int]:
    # 快照由 build_schedule_config_snapshot 严格构建，两项权重已是非负整数。
    return {
        "critical_weight": cfg.graph_critical_weight,
        "impact_weight": cfg.graph_impact_weight,
        "downstream_minutes_weight": cfg.graph_downstream_weight,
    }


def graph_score_requested(score_weights: Dict[str, int]) -> bool:
    return bool(
        score_weights["critical_weight"] > 0
        or score_weights["impact_weight"] > 0
        or score_weights["downstream_minutes_weight"] > 0
    )


def score_available_public_fields(score_weights: Dict[str, int]) -> Dict[str, Any]:
    return {
        "score_enabled": True,
        "score_metric_status": "available",
        "score_disabled_reason": None,
        "score_weight_summary": dict(score_weights),
    }


def build_graph_score_projection(
    *,
    mode: str,
    is_dag: bool,
    score_requested: bool,
    score_weights: Dict[str, int],
    nodes: List[Any],
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
    schedulable_op_ids: Set[int],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    disabled_projection = graph_score_disabled_projection(
        mode=mode,
        is_dag=is_dag,
        score_requested=score_requested,
        score_weights=score_weights,
    )
    if disabled_projection is not None:
        return disabled_projection

    return build_available_graph_score_projection(
        score_weights=score_weights,
        nodes=nodes,
        node_metrics=node_metrics,
        topological_order=topological_order,
        schedulable_op_ids=schedulable_op_ids,
    )


def graph_score_disabled_projection(
    *,
    mode: str,
    is_dag: bool,
    score_requested: bool,
    score_weights: Dict[str, int],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
    if mode != "on":
        return {}, {}, {}
    if not score_requested:
        return score_disabled_projection(
            reason=GRAPH_SCORE_WEIGHTS_ZERO_REASON,
            score_weights=score_weights,
        )
    if not is_dag:
        return score_disabled_projection(
            reason=GRAPH_CYCLE_DISABLED_REASON,
            score_weights=score_weights,
        )
    return None


def score_disabled_projection(
    *,
    reason: str,
    score_weights: Dict[str, int],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    return (
        {"score_enabled": False, "score_disabled_reason": reason},
        {
            "score_enabled": False,
            "score_metric_status": "disabled",
            "score_disabled_reason": reason,
            "score_weight_summary": dict(score_weights),
        },
        {},
    )


def build_available_graph_score_projection(
    *,
    score_weights: Dict[str, int],
    nodes: List[Any],
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
    schedulable_op_ids: Set[int],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    op_id_by_node_id = {node.node_id: node.raw["id"] for node in nodes}
    metrics_by_op_id = {
        op_id: node_metrics[node_id]
        for node_id, op_id in op_id_by_node_id.items()
        if op_id in schedulable_op_ids
    }
    ordered_op_ids = ordered_schedulable_op_ids(
        op_id_by_node_id=op_id_by_node_id,
        topological_order=topological_order,
        schedulable_op_ids=schedulable_op_ids,
    )
    graph_priority_key_by_op_id, score_bonus_by_op_id = build_graph_scores_by_op_id(
        metrics_by_op_id=metrics_by_op_id,
        score_weights=score_weights,
    )

    return (
        {
            "score_enabled": True,
            "score_disabled_reason": None,
            "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
            "node_metrics_by_op_id": metrics_by_op_id,
        },
        score_available_public_fields(score_weights),
        graph_score_sample(
            ordered_op_ids=ordered_op_ids,
            total_count=len(metrics_by_op_id),
            score_bonus_by_op_id=score_bonus_by_op_id,
            graph_priority_key_by_op_id=graph_priority_key_by_op_id,
            node_metrics_by_op_id=metrics_by_op_id,
        ),
    )


def ordered_schedulable_op_ids(
    *,
    op_id_by_node_id: Dict[str, int],
    topological_order: List[str],
    schedulable_op_ids: Set[int],
) -> List[int]:
    """The first _GRAPH_SCORE_SAMPLE_LIMIT schedulable operations in topological order."""
    if not schedulable_op_ids:
        return []
    ordered_op_ids: List[int] = []
    for node_id in topological_order:
        op_id = op_id_by_node_id[node_id]
        if op_id in schedulable_op_ids:
            ordered_op_ids.append(op_id)
            if len(ordered_op_ids) >= _GRAPH_SCORE_SAMPLE_LIMIT:
                break
    return ordered_op_ids


def build_graph_scores_by_op_id(
    *,
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    score_weights: Dict[str, int],
) -> Tuple[Dict[int, Tuple[float, ...]], Dict[int, int]]:
    keys: Dict[int, Tuple[float, ...]] = {}
    bonuses: Dict[int, int] = {}
    for op_id, metric in metrics_by_op_id.items():
        bonus, key = graph_score_components(metric, **score_weights)
        keys[op_id] = key
        bonuses[op_id] = bonus
    return keys, bonuses


def graph_score_sample(
    *,
    ordered_op_ids: List[int],
    total_count: int,
    score_bonus_by_op_id: Dict[int, int],
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]],
    node_metrics_by_op_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "graph_score_sample": [
            _graph_score_sample_row(
                op_id=op_id,
                score_bonus_by_op_id=score_bonus_by_op_id,
                graph_priority_key_by_op_id=graph_priority_key_by_op_id,
                node_metrics_by_op_id=node_metrics_by_op_id,
            )
            for op_id in ordered_op_ids
        ],
        "graph_score_sample_count": total_count,
        "graph_score_sample_truncated": total_count > _GRAPH_SCORE_SAMPLE_LIMIT,
    }


def _graph_score_sample_row(
    *,
    op_id: int,
    score_bonus_by_op_id: Dict[int, int],
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]],
    node_metrics_by_op_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    metric = node_metrics_by_op_id[op_id]
    return {
        "op_id": int(op_id),
        "bonus": int(score_bonus_by_op_id[op_id]),
        "priority_key": list(graph_priority_key_by_op_id[op_id]),
        "is_on_critical_path": bool(metric["is_on_critical_path"]),
        "impact_count": int(metric["impact_count"]),
        "downstream_critical_minutes": int(metric["downstream_critical_minutes"]),
        "bottleneck_machine_score": float(metric["bottleneck_machine_score"]),
    }
