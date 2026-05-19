from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .schedule_input_collector import ScheduleRunInput

GRAPH_CYCLE_DISABLED_REASON = "schedule_graph_cycle"
GRAPH_SCORE_WEIGHTS_ZERO_REASON = "score_weights_zero"

_GRAPH_INPUT_SCOPE = "all_algo_ops_with_frozen_markers"
_GRAPH_SCORE_SAMPLE_LIMIT = 10


def effective_graph_analysis_mode(mode: str) -> str:
    if mode == "on":
        return "report_only"
    return mode


def graph_input_scope(schedule_input: ScheduleRunInput, *, nodes: Optional[List[Any]] = None) -> Dict[str, Any]:
    if nodes is None:
        frozen_node_count = len(schedule_input.frozen_op_ids or set())
    else:
        frozen_node_count = sum(1 for node in nodes if bool(node.is_frozen))
    return {
        "input_scope": _GRAPH_INPUT_SCOPE,
        "total_algo_op_count": int(len(schedule_input.algo_ops or [])),
        "reschedulable_unfrozen_op_count": int(len(schedule_input.algo_ops_to_schedule or [])),
        "frozen_node_count": int(frozen_node_count),
        "seed_result_count": int(len(schedule_input.seed_results or [])),
    }


def graph_score_weight(cfg: Any, field: str) -> int:
    value = getattr(cfg, field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} 必须是非负整数：{value!r}")
    return int(value)


def graph_score_weights(cfg: Any) -> Dict[str, int]:
    critical_weight = graph_score_weight(cfg, "graph_critical_weight")
    impact_weight = graph_score_weight(cfg, "graph_impact_weight")
    downstream_minutes_weight = graph_score_weight(cfg, "graph_downstream_weight")
    return {
        "critical_weight": critical_weight,
        "impact_weight": impact_weight,
        "downstream_minutes_weight": downstream_minutes_weight,
    }


def graph_score_requested(score_weights: Dict[str, int]) -> bool:
    return bool(
        int(score_weights["critical_weight"]) > 0
        or int(score_weights["impact_weight"]) > 0
        or int(score_weights["downstream_minutes_weight"]) > 0
    )


def score_weight_summary(score_weights: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
    if score_weights is None:
        return None
    return {
        "critical_weight": int(score_weights["critical_weight"]),
        "impact_weight": int(score_weights["impact_weight"]),
        "downstream_minutes_weight": int(score_weights["downstream_minutes_weight"]),
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


def graph_cycle_disabled_public_fields() -> Dict[str, Any]:
    return {
        "effective_mode": "sgs_without_graph_ready_queue",
        "graph_enhancement_allowed": False,
        "graph_enhancement_disabled_reason": GRAPH_CYCLE_DISABLED_REASON,
        "ready_queue_enabled": False,
        "graph_enhancement_message": "工序关系里有互相卡住的地方，本次先不用重点工序优先排法，继续按普通排法处理。",
    }


def graph_dispatch_mode_override(public: Dict[str, Any]) -> Optional[str]:
    if public.get("effective_mode") == "sgs_without_graph_ready_queue":
        return "sgs"
    return None


def graph_ready_public_fields(*, mode: str, is_dag: bool, graph_block_on_cycle: str) -> Dict[str, Any]:
    if mode != "on":
        return {}
    if is_dag:
        return {
            "effective_mode": "graph_ready_queue",
            "graph_enhancement_allowed": True,
            "graph_enhancement_disabled_reason": None,
            "ready_queue_enabled": True,
        }
    if graph_block_on_cycle == "no":
        return graph_cycle_disabled_public_fields()
    return {
        "graph_enhancement_allowed": False,
        "graph_enhancement_disabled_reason": GRAPH_CYCLE_DISABLED_REASON,
        "ready_queue_enabled": False,
    }


def node_op_id(node: Any) -> int:
    raw = getattr(node, "raw", {}) or {}
    value = raw.get("id") if isinstance(raw, dict) else None
    if isinstance(value, bool):
        value = None
    try:
        op_id = int(value or 0)
    except (TypeError, ValueError):
        op_id = 0
    if op_id <= 0:
        from core.services.scheduler.graph.input_adapter import GraphInputContractError

        raise GraphInputContractError(f"graph_ready_context 节点缺少有效 op_id：{getattr(node, 'node_id', '-')}")
    return op_id


def positive_op_id_set(values: Any) -> Set[int]:
    result: Set[int] = set()
    for value in values or ():
        if isinstance(value, bool):
            continue
        try:
            op_id = int(value or 0)
        except (TypeError, ValueError):
            continue
        if op_id > 0:
            result.add(op_id)
    return result


def safe_node_op_id_map(nodes: List[Any]) -> Dict[str, int]:
    return {str(node.node_id): int(node_op_id(node)) for node in nodes}


def build_graph_health_context(
    *,
    nodes: List[Any],
    payload: Dict[str, Any],
    schedule_input: ScheduleRunInput,
) -> Dict[str, Any]:
    op_id_by_node_id = safe_node_op_id_map(nodes)
    critical_path_op_ids = [
        int(op_id_by_node_id[node_id])
        for node_id in list(payload.get("critical_path") or [])
        if str(node_id) in op_id_by_node_id
    ]
    schedulable_op_ids = positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])
    scored_top_impact = []
    for raw_node_id, raw_metrics in dict(payload.get("node_metrics") or {}).items():
        op_id = op_id_by_node_id.get(str(raw_node_id))
        if op_id is None or op_id not in schedulable_op_ids:
            continue
        impact_count = int(dict(raw_metrics or {}).get("impact_count") or 0)
        if impact_count > 0:
            scored_top_impact.append((impact_count, int(op_id)))
    scored_top_impact.sort(reverse=True)
    return {
        "critical_path_op_ids": critical_path_op_ids,
        "top_impact_op_ids": [op_id for _impact, op_id in scored_top_impact],
    }


def sort_key_by_op_id(nodes: List[Any], *, schedulable_op_ids: Set[int]) -> Dict[int, Tuple[int, int, int]]:
    batch_order: Dict[str, int] = {}
    for node in sorted(nodes, key=lambda item: (str(item.batch_id), int(item.seq), str(item.op_code), str(item.node_id))):
        batch_order.setdefault(str(node.batch_id), len(batch_order))
    sort_keys: Dict[int, Tuple[int, int, int]] = {}
    for node in nodes:
        op_id = node_op_id(node)
        if op_id in schedulable_op_ids:
            sort_keys[op_id] = (int(batch_order[str(node.batch_id)]), int(node.seq), int(op_id))
    return sort_keys


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
        op_id = node_op_id(node)
        if op_id not in allowed_op_ids:
            continue
        if op_id in result:
            raise GraphInputContractError(f"图评分上下文发现重复 op_id：{op_id}")
        node_id = str(node.node_id)
        if node_id not in node_metrics:
            raise GraphInputContractError(f"图评分缺少工序 {op_id} 的 node_metrics。")
        result[op_id] = dict(node_metrics[node_id])
    missing = sorted(required_op_ids.difference(result))
    if missing:
        raise GraphInputContractError(f"图评分缺少待排工序指标：{missing}")
    return result


def truncated(values: List[Any], limit: int) -> bool:
    return len(values) > int(limit)


def graph_score_sample(
    *,
    ordered_op_ids: List[int],
    score_bonus_by_op_id: Dict[int, int],
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]],
    node_metrics_by_op_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    sample_op_ids = ordered_op_ids[:_GRAPH_SCORE_SAMPLE_LIMIT]
    return {
        "graph_score_sample": [
            {
                "op_id": int(op_id),
                "bonus": int(score_bonus_by_op_id[op_id]),
                "priority_key": list(graph_priority_key_by_op_id[op_id]),
                "is_on_critical_path": bool(node_metrics_by_op_id[op_id]["is_on_critical_path"]),
                "impact_count": int(node_metrics_by_op_id[op_id]["impact_count"]),
                "downstream_critical_minutes": int(node_metrics_by_op_id[op_id]["downstream_critical_minutes"]),
            }
            for op_id in sample_op_ids
        ],
        "graph_score_sample_count": int(len(ordered_op_ids)),
        "graph_score_sample_truncated": truncated(ordered_op_ids, _GRAPH_SCORE_SAMPLE_LIMIT),
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
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    from core.services.scheduler.graph.input_adapter import GraphInputContractError
    from core.services.scheduler.graph.scoring import (
        GraphScoringContractError,
        graph_priority_key_component,
        graph_score_bonus,
    )

    schedulable_op_ids = positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])
    fixed_op_ids = positive_op_id_set(schedule_input.frozen_op_ids or ())
    fixed_op_ids.update(
        positive_op_id_set(
            (item or {}).get("op_id") if isinstance(item, dict) else getattr(item, "op_id", None)
            for item in schedule_input.seed_results or ()
        )
    )
    allowed_op_ids = set(schedulable_op_ids).union(fixed_op_ids)
    metrics_by_op_id = node_metrics_by_op_id(
        nodes=nodes,
        node_metrics=node_metrics,
        allowed_op_ids=allowed_op_ids,
        required_op_ids=set(schedulable_op_ids),
    )
    op_id_by_node_id = {str(node.node_id): node_op_id(node) for node in nodes}
    ordered_op_ids = [
        op_id_by_node_id[node_id]
        for node_id in topological_order
        if op_id_by_node_id.get(node_id) in schedulable_op_ids
    ]
    if not ordered_op_ids:
        ordered_op_ids = sorted(schedulable_op_ids)

    try:
        graph_priority_key_by_op_id = {
            op_id: graph_priority_key_component(metrics_by_op_id[op_id], **score_weights)
            for op_id in sorted(schedulable_op_ids)
        }
        score_bonus_by_op_id = {
            op_id: graph_score_bonus(metrics_by_op_id[op_id], **score_weights)
            for op_id in sorted(schedulable_op_ids)
        }
    except GraphScoringContractError as exc:
        raise GraphInputContractError(f"图评分指标合同错误：{exc}") from exc

    return (
        {
            "score_enabled": True,
            "score_disabled_reason": None,
            "score_weights": dict(score_weights),
            "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
        },
        score_available_public_fields(score_weights),
        graph_score_sample(
            ordered_op_ids=ordered_op_ids,
            score_bonus_by_op_id=score_bonus_by_op_id,
            graph_priority_key_by_op_id=graph_priority_key_by_op_id,
            node_metrics_by_op_id=metrics_by_op_id,
        ),
    )


def build_predecessor_successor_maps(nodes: List[Any], edges: List[Any]) -> Tuple[Dict[int, Set[int]], Dict[int, Set[int]]]:
    from core.services.scheduler.graph.input_adapter import GraphInputContractError

    def _edge_node_id(edge: Any, attr: str, index: int) -> str:
        if not hasattr(edge, attr):
            raise GraphInputContractError(f"图 ready 队列边缺少字段 {attr}：edge_index={index}")
        node_id = str(getattr(edge, attr) or "").strip()
        if not node_id:
            raise GraphInputContractError(f"图 ready 队列边字段 {attr} 不能为空：edge_index={index}")
        return node_id

    op_id_by_node_id = {str(node.node_id): node_op_id(node) for node in nodes}
    predecessors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    successors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    for index, edge in enumerate(edges):
        from_node_id = _edge_node_id(edge, "from_node_id", index)
        to_node_id = _edge_node_id(edge, "to_node_id", index)
        if from_node_id not in op_id_by_node_id:
            raise GraphInputContractError(
                f"图 ready 队列边引用未知前置节点：from_node_id={from_node_id!r}，edge_index={index}"
            )
        if to_node_id not in op_id_by_node_id:
            raise GraphInputContractError(
                f"图 ready 队列边引用未知后置节点：to_node_id={to_node_id!r}，edge_index={index}"
            )
        from_op_id = op_id_by_node_id[from_node_id]
        to_op_id = op_id_by_node_id[to_node_id]
        predecessors.setdefault(to_op_id, set()).add(from_op_id)
        successors.setdefault(from_op_id, set()).add(to_op_id)
    return predecessors, successors


def build_graph_ready_context(
    schedule_input: ScheduleRunInput,
    *,
    nodes: List[Any],
    edges: List[Any],
    enabled: bool,
    score_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not enabled:
        return None
    schedulable_op_ids = positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])
    fixed_op_ids = positive_op_id_set(schedule_input.frozen_op_ids or ())
    fixed_op_ids.update(
        positive_op_id_set(
            (item or {}).get("op_id") if isinstance(item, dict) else getattr(item, "op_id", None)
            for item in schedule_input.seed_results or ()
        )
    )
    predecessor_map, successor_map = build_predecessor_successor_maps(nodes, edges)
    context = {
        "enabled": True,
        "disabled_reason": None,
        "schedulable_op_ids": set(schedulable_op_ids),
        "fixed_op_ids": set(fixed_op_ids),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": sort_key_by_op_id(nodes, schedulable_op_ids=schedulable_op_ids),
    }
    if score_context:
        context.update(dict(score_context))
    return context
