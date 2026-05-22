from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .schedule_graph_dispatch_context import build_predecessor_successor_maps, node_op_id, positive_op_id_set
from .schedule_input_collector import ScheduleRunInput

GRAPH_RESOURCE_NOT_DAG_REASON = "graph_not_dag"
GRAPH_RESOURCE_ENHANCEMENT_DISABLED_REASON = "graph_enhancement_disabled"
GRAPH_RESOURCE_MATCHING_CONTRACT_REASON = "graph_resource_matching_contract_error"


def _schedule_input_schedulable_op_ids(schedule_input: ScheduleRunInput) -> Set[int]:
    return positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])


def _schedule_input_fixed_op_ids(schedule_input: ScheduleRunInput) -> Set[int]:
    fixed_op_ids = positive_op_id_set(schedule_input.frozen_op_ids or ())
    fixed_op_ids.update(
        positive_op_id_set(
            (item or {}).get("op_id") if isinstance(item, dict) else getattr(item, "op_id", None)
            for item in schedule_input.seed_results or ()
        )
    )
    return fixed_op_ids


def _ready_context_predecessor_map(graph_ready_context: Dict[str, Any]) -> Dict[int, Set[int]]:
    raw_map = graph_ready_context.get("predecessor_op_ids_by_op_id")
    if not isinstance(raw_map, dict):
        from core.services.scheduler.graph.input_adapter import GraphInputContractError

        raise GraphInputContractError("graph_ready_context 缺少 predecessor_op_ids_by_op_id。")
    result: Dict[int, Set[int]] = {}
    for raw_op_id, raw_predecessors in raw_map.items():
        try:
            op_id = int(raw_op_id)
        except (TypeError, ValueError):
            op_id = 0
        if op_id <= 0:
            from core.services.scheduler.graph.input_adapter import GraphInputContractError

            raise GraphInputContractError(f"graph_ready_context 包含无效 op_id：{raw_op_id!r}")
        result[op_id] = positive_op_id_set(raw_predecessors or ())
    return result


def build_first_wave_ready_nodes(
    schedule_input: ScheduleRunInput,
    *,
    nodes: List[Any],
    edges: List[Any],
    graph_ready_context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    if graph_ready_context is None:
        schedulable_op_ids = _schedule_input_schedulable_op_ids(schedule_input)
        fixed_op_ids = _schedule_input_fixed_op_ids(schedule_input)
        predecessor_map, _successor_map = build_predecessor_successor_maps(nodes, edges)
    else:
        schedulable_op_ids = positive_op_id_set(graph_ready_context.get("schedulable_op_ids") or ())
        fixed_op_ids = positive_op_id_set(graph_ready_context.get("fixed_op_ids") or ())
        predecessor_map = _ready_context_predecessor_map(graph_ready_context)

    ready_op_ids = {
        op_id
        for op_id in schedulable_op_ids
        if set(predecessor_map.get(op_id, set())).issubset(fixed_op_ids)
    }
    return [node for node in nodes if node_op_id(node) in ready_op_ids]


def _resource_matching_status_projection(*, status: str, reason: str) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "ready_operation_count": 0,
        "operation_with_candidate_count": 0,
        "machine_count": 0,
        "edge_count": 0,
        "matched_operation_count": 0,
        "unmatched_operation_count": 0,
        "bottleneck_machine_count": 0,
    }


def build_graph_resource_matching_projection(
    *,
    mode: str,
    is_dag: bool,
    graph_enhancement_allowed: bool,
    graph_enhancement_disabled_reason: Optional[str],
    schedule_input: ScheduleRunInput,
    nodes: List[Any],
    edges: List[Any],
    graph_ready_context: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not is_dag:
        return _resource_matching_status_projection(
            status="skipped",
            reason=GRAPH_RESOURCE_NOT_DAG_REASON,
        ), {}
    if mode == "on" and (not graph_enhancement_allowed or graph_ready_context is None):
        return _resource_matching_status_projection(
            status="skipped",
            reason=str(graph_enhancement_disabled_reason or GRAPH_RESOURCE_ENHANCEMENT_DISABLED_REASON),
        ), {}

    from core.services.scheduler.graph.resource_matching import (
        GraphResourceMatchingContractError,
        resource_matching_summary_to_diagnostics_dict,
        resource_matching_summary_to_public_dict,
        summarize_operation_machine_matching,
    )

    ready_nodes = build_first_wave_ready_nodes(
        schedule_input,
        nodes=nodes,
        edges=edges,
        graph_ready_context=(graph_ready_context if mode == "on" else None),
    )
    try:
        summary = summarize_operation_machine_matching(ready_nodes)
    except GraphResourceMatchingContractError:
        return _resource_matching_status_projection(
            status="error",
            reason=GRAPH_RESOURCE_MATCHING_CONTRACT_REASON,
        ), {}
    return resource_matching_summary_to_public_dict(summary), resource_matching_summary_to_diagnostics_dict(summary)


__all__ = [
    "build_first_wave_ready_nodes",
    "build_graph_resource_matching_projection",
]
