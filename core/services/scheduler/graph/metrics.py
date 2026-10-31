from __future__ import annotations

import math
from typing import Any, Dict, FrozenSet, List, Set, Tuple

from .impact_counts import compute_impact_counts_by_node as _compute_impact_counts_by_node
from .nx_runtime import import_networkx

_SOURCE_NODE_ID = "__GRAPH_METRICS_SOURCE__"


def node_sort_key(graph: Any, node_id: str) -> Tuple[str, int, str, str]:
    data = graph.nodes[node_id]
    return (
        str(data["batch_id"]),
        int(data["seq"]),
        str(data["op_code"]),
        str(node_id),
    )


def get_topological_generations(graph: Any) -> List[List[str]]:
    nx = import_networkx()
    return [
        sorted(list(group), key=lambda node_id: node_sort_key(graph, node_id))
        for group in nx.topological_generations(graph)
    ]


def _duration_of(graph: Any, node_id: str) -> int:
    return int(graph.nodes[node_id]["duration_minutes"])


def _repeated_external_group_bit_by_key(graph: Any) -> Dict[Tuple[str, ...], int]:
    seen: Set[Tuple[str, ...]] = set()
    repeated: Dict[Tuple[str, ...], int] = {}
    for node_id in graph.nodes:
        key = graph.nodes[node_id]["external_group_key"]
        if key is None:
            continue
        if key in seen:
            if key not in repeated:
                repeated[key] = 1 << len(repeated)
        else:
            seen.add(key)
    return repeated


def _external_group_bit_of(
    graph: Any,
    node_id: str,
    group_bit_by_key: Dict[Tuple[str, ...], int],
) -> int:
    if not group_bit_by_key:
        return 0
    key = graph.nodes[node_id]["external_group_key"]
    return group_bit_by_key[key] if key in group_bit_by_key else 0


def _future_external_group_mask_by_node(
    graph: Any,
    *,
    topological_order: List[str],
    group_bit_by_key: Dict[Tuple[str, ...], int],
) -> Dict[str, int]:
    if not group_bit_by_key:
        return {node_id: 0 for node_id in topological_order}
    future_by_node: Dict[str, int] = {}
    for node_id in reversed(topological_order):
        mask = 0
        for succ_id in graph.succ[node_id]:
            mask |= future_by_node[succ_id] | _external_group_bit_of(graph, succ_id, group_bit_by_key)
        future_by_node[node_id] = mask
    return future_by_node


def _past_external_group_mask_by_node(
    graph: Any,
    *,
    topological_order: List[str],
    group_bit_by_key: Dict[Tuple[str, ...], int],
) -> Dict[str, int]:
    if not group_bit_by_key:
        return {node_id: 0 for node_id in topological_order}
    past_by_node: Dict[str, int] = {}
    for node_id in topological_order:
        mask = 0
        for pred_id in graph.pred[node_id]:
            mask |= past_by_node[pred_id] | _external_group_bit_of(graph, pred_id, group_bit_by_key)
        past_by_node[node_id] = mask
    return past_by_node


def get_critical_path(
    graph: Any,
    *,
    topological_order: List[str],
) -> Tuple[List[str], int]:
    # The former weighted copy inserted incoming edges by source-node order.
    # Keep that predecessor tie order while reading the original graph's edges.
    node_index = {node_id: index for index, node_id in enumerate(graph.nodes)}
    group_bit_by_key = _repeated_external_group_bit_by_key(graph)
    future_mask_by_node = _future_external_group_mask_by_node(
        graph,
        topological_order=topological_order,
        group_bit_by_key=group_bit_by_key,
    )
    states: Dict[str, Dict[int, Tuple[int, str, int]]] = {
        _SOURCE_NODE_ID: {0: (0, _SOURCE_NODE_ID, 0)}
    }
    best_by_node: Dict[str, Tuple[int, str, int]] = {
        _SOURCE_NODE_ID: (0, _SOURCE_NODE_ID, 0)
    }
    for node_id in topological_order:
        duration = _duration_of(graph, node_id)
        group_bit = _external_group_bit_of(graph, node_id, group_bit_by_key)
        future_mask = future_mask_by_node[node_id]
        predecessors = graph.pred[node_id]
        node_states: Dict[int, Tuple[int, str, int]] = {}
        if predecessors:
            for parent_id, data in predecessors.items():
                lag = int(data["lag_minutes"])
                for parent_mask, (parent_minutes, _grandparent_id, _grandparent_mask) in states[parent_id].items():
                    if group_bit and (parent_mask & group_bit):
                        added = 0
                        raw_next_mask = parent_mask
                    else:
                        added = duration
                        raw_next_mask = parent_mask | group_bit
                    next_mask = raw_next_mask & future_mask
                    candidate = (parent_minutes + added + lag, parent_id, parent_mask)
                    existing = node_states.get(next_mask)
                    if existing is None or (candidate[0], -node_index[candidate[1]]) > (
                        existing[0],
                        -node_index[existing[1]],
                    ):
                        node_states[next_mask] = candidate
            best_mask, best_state = max(
                node_states.items(),
                key=lambda item: (item[1][0], -node_index[item[1][1]]),
            )
            best_by_node[node_id] = (best_state[0], best_state[1], best_mask)
        else:
            next_mask = group_bit & future_mask
            node_states[next_mask] = (duration, _SOURCE_NODE_ID, 0)
            best_by_node[node_id] = (duration, _SOURCE_NODE_ID, next_mask)
        states[node_id] = node_states

    # Source comes first, so a graph with no positive distance has an empty path.
    node_id = max(best_by_node, key=lambda item: best_by_node[item][0])
    minutes, _parent_id, mask = best_by_node[node_id]
    path: List[str] = []
    while node_id is not _SOURCE_NODE_ID:
        path.append(node_id)
        _step_minutes, parent_id, parent_mask = states[node_id][mask]
        node_id, mask = parent_id, parent_mask
    path.reverse()

    return path, minutes


def _build_downstream_critical_minutes_by_node(
    graph: Any,
    *,
    topological_order: List[str],
) -> Dict[str, int]:
    group_bit_by_key = _repeated_external_group_bit_by_key(graph)
    past_mask_by_node = _past_external_group_mask_by_node(
        graph,
        topological_order=topological_order,
        group_bit_by_key=group_bit_by_key,
    )
    empty_groups: FrozenSet[Tuple[int, int]] = frozenset()
    states: Dict[str, Dict[FrozenSet[Tuple[int, int]], int]] = {}
    result: Dict[str, int] = {}
    for node_id in reversed(topological_order):
        duration = _duration_of(graph, node_id)
        group_bit = _external_group_bit_of(graph, node_id, group_bit_by_key)
        past_mask = past_mask_by_node[node_id]
        out_edges = list(graph.out_edges(node_id, data=True))
        if not out_edges:
            groups = (
                empty_groups
                if not (group_bit & past_mask)
                else frozenset(((group_bit, duration),))
            )
            states[node_id] = {groups: duration}
            result[node_id] = duration
            continue
        node_states: Dict[FrozenSet[Tuple[int, int]], int] = {}
        for _from_node_id, to_node_id, data in out_edges:
            lag = int(data["lag_minutes"])
            for to_groups, to_minutes in states[to_node_id].items():
                if not group_bit:
                    added = duration
                    raw_next_groups = to_groups
                else:
                    credited = next((item_dur for item_bit, item_dur in to_groups if item_bit == group_bit), None)
                    if credited is None:
                        added = duration
                        raw_next_groups = to_groups | {(group_bit, duration)}
                    else:
                        added = duration - credited
                        raw_next_groups = (
                            to_groups
                            if credited == duration
                            else frozenset(
                                (item_bit, duration if item_bit == group_bit else item_dur)
                                for item_bit, item_dur in to_groups
                            )
                        )
                next_groups = (
                    frozenset(item for item in raw_next_groups if past_mask & item[0])
                    if raw_next_groups and past_mask
                    else empty_groups
                )
                total = to_minutes + lag + added
                existing = node_states.get(next_groups)
                if existing is None or total > existing:
                    node_states[next_groups] = total
        states[node_id] = node_states
        result[node_id] = max(node_states.values())
    return result


def _machine_ids_for_node(data: Dict[str, Any]) -> Tuple[str, ...]:
    # Candidate ids are already compact text (OperationGraphNode.__post_init__).
    ids: List[str] = list(data["candidate_machine_ids"])
    raw_machine = data["machine_id"]
    machine_id = "" if raw_machine is None else str(raw_machine)
    if machine_id.strip():
        ids.append(machine_id)
    return tuple(dict.fromkeys(ids))


def _build_bottleneck_machine_score_by_node(graph: Any) -> Dict[str, float]:
    machine_ids_by_node: Dict[str, Tuple[str, ...]] = {}
    load_minutes_by_machine: Dict[str, float] = {}
    for node_id in graph.nodes:
        machine_ids = _machine_ids_for_node(graph.nodes[node_id])
        machine_ids_by_node[node_id] = machine_ids
        duration_minutes = _duration_of(graph, node_id)
        if not machine_ids:
            continue
        shared_minutes = float(duration_minutes) / float(len(machine_ids))
        for machine_id in machine_ids:
            load_minutes_by_machine[machine_id] = load_minutes_by_machine.get(machine_id, 0.0) + shared_minutes

    result: Dict[str, float] = {}
    for node_id, machine_ids in machine_ids_by_node.items():
        if not machine_ids:
            result[node_id] = 0.0
            continue
        min_candidate_load = min(load_minutes_by_machine[machine_id] for machine_id in machine_ids)
        flexibility_discount = math.sqrt(float(len(machine_ids)))
        result[node_id] = round((min_candidate_load / 60.0) / flexibility_discount, 6)
    return result


def build_node_metrics(
    graph: Any,
    *,
    topological_order: List[str],
    critical_path: List[str],
    generation_index: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    critical_set = set(critical_path)
    critical_rank = {
        node_id: index
        for index, node_id in enumerate(critical_path)
    }
    impact_count_by_node = _compute_impact_counts_by_node(graph, topological_order)
    downstream_critical_minutes = _build_downstream_critical_minutes_by_node(
        graph,
        topological_order=topological_order,
    )
    bottleneck_machine_score_by_node = _build_bottleneck_machine_score_by_node(graph)

    result: Dict[str, Dict[str, Any]] = {}

    for node_id in graph.nodes:
        result[node_id] = {
            "is_on_critical_path": node_id in critical_set,
            "critical_path_rank": critical_rank.get(node_id),
            "impact_count": impact_count_by_node[node_id],
            "generation_index": generation_index[node_id],
            "downstream_critical_minutes": downstream_critical_minutes[node_id],
            "bottleneck_machine_score": bottleneck_machine_score_by_node[node_id],
        }

    return result


__all__ = [
    "build_node_metrics",
    "get_critical_path",
    "get_topological_generations",
    "node_sort_key",
]
