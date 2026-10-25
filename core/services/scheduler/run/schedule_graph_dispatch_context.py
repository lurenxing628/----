from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode

from .schedule_input_contracts import ScheduleRunInput

GRAPH_CYCLE_DISABLED_REASON = "schedule_graph_cycle"
_GRAPH_INPUT_SCOPE = "all_algo_ops_with_frozen_markers"


def effective_graph_analysis_mode(mode: str) -> str:
    if mode == "on":
        return "report_only"
    return mode


def graph_input_scope(
    schedule_input: ScheduleRunInput, *, nodes: Optional[List[OperationGraphNode]] = None,
) -> Dict[str, Any]:
    if nodes is None:
        frozen_node_count = len(schedule_input.frozen_op_ids)
    else:
        frozen_node_count = sum(1 for node in nodes if node.is_frozen)
    return {
        "input_scope": _GRAPH_INPUT_SCOPE,
        "total_algo_op_count": len(schedule_input.algo_ops),
        "reschedulable_unfrozen_op_count": len(schedule_input.algo_ops_to_schedule),
        "frozen_node_count": frozen_node_count,
        "seed_result_count": len(schedule_input.seed_results),
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


def schedule_input_op_id_sets(schedule_input: ScheduleRunInput) -> Tuple[Set[int], Set[int], Set[int]]:
    schedulable_op_ids = {op.id for op in schedule_input.algo_ops_to_schedule}
    seed_op_ids = {seed["op_id"] for seed in schedule_input.seed_results}
    return schedulable_op_ids, schedule_input.frozen_op_ids | seed_op_ids, seed_op_ids


def sort_key_by_op_id(nodes: List[OperationGraphNode], *, schedulable_op_ids: Set[int]) -> Dict[int, Tuple[int, int, int]]:
    batch_order: Dict[str, int] = {}
    for node in sorted(nodes, key=lambda item: (item.batch_id, item.seq, item.op_code, item.node_id)):
        batch_order.setdefault(node.batch_id, len(batch_order))
    sort_keys: Dict[int, Tuple[int, int, int]] = {}
    for node in nodes:
        op_id = node.raw["id"]
        if op_id in schedulable_op_ids:
            sort_keys[op_id] = (batch_order[node.batch_id], node.seq, op_id)
    return sort_keys


def build_predecessor_successor_maps(
    nodes: List[OperationGraphNode], edges: List[OperationGraphEdge],
) -> Tuple[Dict[int, Set[int]], Dict[int, Set[int]]]:
    # 边由同一批节点构造（线性链或分件图），两端节点编号必在本次节点里。
    op_id_by_node_id = {node.node_id: node.raw["id"] for node in nodes}
    predecessors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    successors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    for edge in edges:
        from_op_id = op_id_by_node_id[edge.from_node_id]
        to_op_id = op_id_by_node_id[edge.to_node_id]
        predecessors[to_op_id].add(from_op_id)
        successors[from_op_id].add(to_op_id)
    return predecessors, successors


def build_graph_ready_context(
    schedule_input: ScheduleRunInput,
    *,
    nodes: List[OperationGraphNode],
    edges: List[OperationGraphEdge],
    enabled: bool,
    score_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not enabled:
        return None
    schedulable_op_ids, fixed_op_ids, seed_op_ids = schedule_input_op_id_sets(schedule_input)
    predecessor_map, successor_map = build_predecessor_successor_maps(nodes, edges)
    context = {
        "enabled": True,
        "disabled_reason": None,
        "schedulable_op_ids": set(schedulable_op_ids),
        "fixed_op_ids": set(fixed_op_ids),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": sort_key_by_op_id(nodes, schedulable_op_ids=schedulable_op_ids),
        "fixed_op_sources_by_op_id": {op_id: ("seed" if op_id in seed_op_ids else "frozen") for op_id in sorted(fixed_op_ids)},
    }
    if score_context:
        context.update(score_context)
    return context
