from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .schedule_input_contracts import ScheduleRunInput

GRAPH_CYCLE_DISABLED_REASON = "schedule_graph_cycle"
_GRAPH_INPUT_SCOPE = "all_algo_ops_with_frozen_markers"


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


def schedule_input_op_id_sets(schedule_input: ScheduleRunInput) -> Tuple[Set[int], Set[int], Set[int]]:
    schedulable_op_ids = positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])
    frozen_op_ids = positive_op_id_set(schedule_input.frozen_op_ids or ())
    seed_op_ids = positive_op_id_set(
        (item or {}).get("op_id") if isinstance(item, dict) else getattr(item, "op_id", None)
        for item in schedule_input.seed_results or ()
    )
    return schedulable_op_ids, frozen_op_ids | seed_op_ids, seed_op_ids


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
