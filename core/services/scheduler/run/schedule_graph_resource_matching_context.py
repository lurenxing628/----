from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .schedule_graph_dispatch_context import build_predecessor_successor_maps, schedule_input_op_id_sets
from .schedule_input_contracts import ScheduleRunInput

GRAPH_RESOURCE_NOT_DAG_REASON = "graph_not_dag"
GRAPH_RESOURCE_MATCHING_CONTRACT_REASON = "graph_resource_matching_contract_error"


def build_first_wave_ready_nodes(
    schedule_input: ScheduleRunInput,
    *,
    nodes: List[Any],
    edges: List[Any],
    graph_ready_context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    if graph_ready_context is None:
        schedulable_op_ids, fixed_op_ids, _ = schedule_input_op_id_sets(schedule_input)
        predecessor_map, _successor_map = build_predecessor_successor_maps(nodes, edges)
    else:
        schedulable_op_ids = graph_ready_context["schedulable_op_ids"]
        fixed_op_ids = graph_ready_context["fixed_op_ids"]
        predecessor_map = graph_ready_context["predecessor_op_ids_by_op_id"]

    ready_op_ids = {
        op_id
        for op_id in schedulable_op_ids
        if predecessor_map.get(op_id, set()).issubset(fixed_op_ids)
    }
    return [node for node in nodes if node.raw["id"] in ready_op_ids]


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
