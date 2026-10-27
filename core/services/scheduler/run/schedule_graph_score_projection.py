from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

from .schedule_graph_dispatch_context import (
    GRAPH_CYCLE_DISABLED_REASON,
    schedule_input_op_id_sets,
)
from .schedule_input_contracts import ScheduleRunInput

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


def score_weight_summary(score_weights: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
    if score_weights is None:
        return None
    return {
        "critical_weight": score_weights["critical_weight"],
        "impact_weight": score_weights["impact_weight"],
        "downstream_minutes_weight": score_weights["downstream_minutes_weight"],
    }


def score_disabled_public_fields(
    *,
    reason: str,
    score_weights: Optional[Dict[str, int]],
    metric_status: str = "disabled",
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "score_enabled": False,
        "score_metric_status": metric_status,
        "score_disabled_reason": reason,
    }
    summary = score_weight_summary(score_weights)
    if summary is not None:
        fields["score_weight_summary"] = summary
    return fields


def score_available_public_fields(score_weights: Dict[str, int]) -> Dict[str, Any]:
    return {
        "score_enabled": True,
        "score_metric_status": "available",
        "score_disabled_reason": None,
        "score_weight_summary": score_weight_summary(score_weights),
    }


def build_graph_score_projection(
    *,
    mode: str,
    is_dag: bool,
    score_requested: bool,
    score_weights: Optional[Dict[str, int]],
    nodes: List[Any],
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
    schedule_input: ScheduleRunInput,
    op_id_sets: Optional[Tuple[Set[int], Set[int], Set[int]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    disabled_projection = graph_score_disabled_projection(
        mode=mode,
        is_dag=is_dag,
        score_requested=score_requested,
        score_weights=score_weights,
    )
    if disabled_projection is not None:
        return disabled_projection
    if score_weights is None:
        raise ValueError("图评分权重缺失。")

    return build_available_graph_score_projection(
        score_weights=score_weights,
        nodes=nodes,
        node_metrics=node_metrics,
        topological_order=topological_order,
        schedule_input=schedule_input,
        op_id_sets=op_id_sets,
    )


def graph_score_disabled_projection(
    *,
    mode: str,
    is_dag: bool,
    score_requested: bool,
    score_weights: Optional[Dict[str, int]],
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
    score_weights: Optional[Dict[str, int]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    return (
        {"score_enabled": False, "score_disabled_reason": reason},
        score_disabled_public_fields(
            reason=reason,
            score_weights=score_weights,
        ),
        {},
    )


def build_available_graph_score_projection(
    *,
    score_weights: Dict[str, int],
    nodes: List[Any],
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
    schedule_input: ScheduleRunInput,
    op_id_sets: Optional[Tuple[Set[int], Set[int], Set[int]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    from core.services.scheduler.graph.scoring import graph_score_components

    schedulable_op_ids, fixed_op_ids, _ = op_id_sets or schedule_input_op_id_sets(schedule_input)
    allowed_op_ids = schedulable_op_ids | fixed_op_ids
    metrics_by_op_id = node_metrics_by_op_id(
        nodes=nodes,
        node_metrics=node_metrics,
        allowed_op_ids=allowed_op_ids,
        required_op_ids=schedulable_op_ids,
    )
    ordered_op_ids = ordered_schedulable_op_ids(
        nodes=nodes,
        topological_order=topological_order,
        schedulable_op_ids=schedulable_op_ids,
    )
    graph_priority_key_by_op_id, score_bonus_by_op_id = build_graph_scores_by_op_id(
        metrics_by_op_id=metrics_by_op_id,
        schedulable_op_ids=schedulable_op_ids,
        score_weights=score_weights,
        score_components_fn=graph_score_components,
    )

    return (
        {
            "score_enabled": True,
            "score_disabled_reason": None,
            "score_weights": dict(score_weights),
            "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
            "node_metrics_by_op_id": {op_id: metrics_by_op_id[op_id] for op_id in sorted(schedulable_op_ids)},
        },
        score_available_public_fields(score_weights),
        graph_score_sample(
            ordered_op_ids=ordered_op_ids,
            total_count=len(schedulable_op_ids),
            score_bonus_by_op_id=score_bonus_by_op_id,
            graph_priority_key_by_op_id=graph_priority_key_by_op_id,
            node_metrics_by_op_id=metrics_by_op_id,
        ),
    )


def node_metrics_by_op_id(
    *,
    nodes: List[Any],
    node_metrics: Dict[str, Dict[str, Any]],
    allowed_op_ids: Set[int],
    required_op_ids: Set[int],
) -> Dict[int, Dict[str, Any]]:
    from core.services.scheduler.graph.input_adapter import GraphInputContractError

    result: Dict[int, Dict[str, Any]] = {}
    for node in nodes:
        op_id = node.raw["id"]
        if op_id not in allowed_op_ids:
            continue
        if op_id in result:
            raise GraphInputContractError(f"图评分上下文发现重复 op_id：{op_id}")
        node_id = str(node.node_id)
        if node_id not in node_metrics:
            raise GraphInputContractError(f"图评分缺少工序 {op_id} 的 node_metrics。")
        result[op_id] = node_metrics[node_id]
    missing = sorted(required_op_ids.difference(result))
    if missing:
        raise GraphInputContractError(f"图评分缺少待排工序指标：{missing}")
    return result


def ordered_schedulable_op_ids(
    *,
    nodes: List[Any],
    topological_order: List[str],
    schedulable_op_ids: Set[int],
) -> List[int]:
    """The first _GRAPH_SCORE_SAMPLE_LIMIT schedulable operations in topological order."""
    if not schedulable_op_ids:
        return []
    op_id_by_node_id = {str(node.node_id): node.raw["id"] for node in nodes}
    ordered_op_ids: List[int] = []
    for node_id in topological_order:
        op_id = op_id_by_node_id.get(node_id)
        if op_id is not None and op_id in schedulable_op_ids:
            ordered_op_ids.append(op_id)
            if len(ordered_op_ids) >= _GRAPH_SCORE_SAMPLE_LIMIT:
                return ordered_op_ids
    if ordered_op_ids:
        return ordered_op_ids
    return sorted(schedulable_op_ids)[:_GRAPH_SCORE_SAMPLE_LIMIT]


def build_graph_scores_by_op_id(
    *,
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    schedulable_op_ids: Set[int],
    score_weights: Dict[str, int],
    score_components_fn: Any,
) -> Tuple[Dict[int, Tuple[float, ...]], Dict[int, int]]:
    keys: Dict[int, Tuple[float, ...]] = {}
    bonuses: Dict[int, int] = {}
    for op_id in sorted(schedulable_op_ids):
        bonus, key = score_components_fn(metrics_by_op_id[op_id], **score_weights)
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
    sample_op_ids = ordered_op_ids[:_GRAPH_SCORE_SAMPLE_LIMIT]
    count = total_count
    return {
        "graph_score_sample": [
            _graph_score_sample_row(
                op_id=op_id,
                score_bonus_by_op_id=score_bonus_by_op_id,
                graph_priority_key_by_op_id=graph_priority_key_by_op_id,
                node_metrics_by_op_id=node_metrics_by_op_id,
            )
            for op_id in sample_op_ids
        ],
        "graph_score_sample_count": count,
        "graph_score_sample_truncated": count > _GRAPH_SCORE_SAMPLE_LIMIT,
    }


def _graph_score_sample_row(
    *,
    op_id: int,
    score_bonus_by_op_id: Dict[int, int],
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]],
    node_metrics_by_op_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    metric = node_metrics_by_op_id[op_id]
    row = {
        "op_id": int(op_id),
        "bonus": int(score_bonus_by_op_id[op_id]),
        "priority_key": list(graph_priority_key_by_op_id[op_id]),
        "is_on_critical_path": bool(metric["is_on_critical_path"]),
        "impact_count": int(metric["impact_count"]),
        "downstream_critical_minutes": int(metric["downstream_critical_minutes"]),
    }
    if "bottleneck_machine_score" in metric:
        row["bottleneck_machine_score"] = float(metric["bottleneck_machine_score"])
    return row
