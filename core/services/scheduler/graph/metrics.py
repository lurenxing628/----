from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

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


def get_topological_order(graph: Any) -> List[str]:
    return [
        node_id
        for group in get_topological_generations(graph)
        for node_id in group
    ]


def get_topological_generations(graph: Any) -> List[List[str]]:
    nx = import_networkx()
    return [
        sorted(list(group), key=lambda node_id: node_sort_key(graph, node_id))
        for group in nx.topological_generations(graph)
    ]


def _duration_of(graph: Any, node_id: str) -> int:
    return int(graph.nodes[node_id]["duration_minutes"])


def get_critical_path(
    graph: Any,
    *,
    topological_order: Optional[List[str]] = None,
) -> Tuple[List[str], int]:
    if topological_order is None:
        topological_order = get_topological_order(graph)

    # The former weighted copy inserted incoming edges by source-node order.
    # Keep that predecessor tie order while reading the original graph's edges.
    node_index = {node_id: index for index, node_id in enumerate(graph.nodes)}
    distances: Dict[str, Tuple[int, str]] = {_SOURCE_NODE_ID: (0, _SOURCE_NODE_ID)}
    for node_id in topological_order:
        duration = _duration_of(graph, node_id)
        predecessors = graph.pred[node_id]
        if predecessors:
            best = max(
                ((distances[parent_id][0] + duration + int(data["lag_minutes"]), parent_id)
                 for parent_id, data in predecessors.items()),
                key=lambda item: (item[0], -node_index[item[1]]),
            )
        else:
            best = (duration, _SOURCE_NODE_ID)
        distances[node_id] = best if best[0] >= 0 else (0, node_id)

    # Source comes first, so a graph with no positive distance has an empty path.
    node_id = max(distances, key=lambda item: distances[item][0])
    minutes = distances[node_id][0]
    path: List[str] = []
    while node_id != _SOURCE_NODE_ID:
        path.append(node_id)
        predecessor = distances[node_id][1]
        if predecessor == node_id:
            break
        node_id = predecessor
    path.reverse()

    return path, minutes


def _build_downstream_critical_minutes_by_node(
    graph: Any,
    *,
    topological_order: List[str],
) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for node_id in reversed(topological_order):
        result[node_id] = _duration_of(graph, node_id) + max(
            (int(data["lag_minutes"]) + result[to_node_id] for _from_node_id, to_node_id, data in graph.out_edges(node_id, data=True)),
            default=0,
        )
    return result


def _machine_ids_for_node(data: Dict[str, Any]) -> Tuple[str, ...]:
    ids: List[str] = []
    for raw in data.get("candidate_machine_ids") or ():
        text = str(raw or "").strip()
        if text:
            ids.append(text)
    machine_id = str(data.get("machine_id") or "").strip()
    if machine_id:
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
    topological_order: Optional[List[str]] = None,
    critical_path: Optional[List[str]] = None,
    generation_index: Optional[Dict[str, int]] = None,
) -> Dict[str, Dict[str, Any]]:
    if topological_order is None:
        generations = get_topological_generations(graph)
        topological_order = [node_id for group in generations for node_id in group]
        if generation_index is None:
            generation_index = {
                node_id: index
                for index, group in enumerate(generations)
                for node_id in group
            }
    elif generation_index is None:
        generation_index = {}
        for node_id in topological_order:
            generation_index[node_id] = max(
                (generation_index[parent_id] + 1 for parent_id in graph.pred[node_id]),
                default=0,
            )
    if critical_path is None:
        critical_path, _critical_minutes = get_critical_path(
            graph, topological_order=topological_order,
        )

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
    "get_topological_order",
    "node_sort_key",
]
