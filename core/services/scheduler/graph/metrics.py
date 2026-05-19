from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .nx_runtime import import_networkx

_SOURCE_NODE_ID = "__GRAPH_METRICS_SOURCE__"


def _node_sort_key(graph: Any, node_id: str) -> Tuple[str, int, str, str]:
    if node_id == _SOURCE_NODE_ID:
        return ("", -1, "", str(node_id))
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
        sorted(list(group), key=lambda node_id: _node_sort_key(graph, node_id))
        for group in nx.topological_generations(graph)
    ]


def get_generation_index(graph: Any) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for index, group in enumerate(get_topological_generations(graph)):
        for node_id in group:
            result[node_id] = index

    return result


def _duration_of(graph: Any, node_id: str) -> int:
    return int(graph.nodes[node_id]["duration_minutes"])


def build_duration_weighted_graph(graph: Any) -> Any:
    nx = import_networkx()

    weighted = nx.DiGraph()
    weighted.add_node(_SOURCE_NODE_ID)

    for node_id, data in graph.nodes(data=True):
        weighted.add_node(node_id, **dict(data))

    for node_id in graph.nodes:
        if graph.in_degree(node_id) == 0:
            weighted.add_edge(_SOURCE_NODE_ID, node_id, weight=_duration_of(graph, node_id))

    for from_node_id, to_node_id, data in graph.edges(data=True):
        lag_minutes = int(data["lag_minutes"])
        weighted.add_edge(from_node_id, to_node_id, weight=_duration_of(graph, to_node_id) + lag_minutes)

    return weighted


def _path_weight(graph: Any, path: List[str]) -> int:
    total = 0
    for from_node_id, to_node_id in zip(path, path[1:]):
        total += int(graph.edges[from_node_id, to_node_id]["weight"])
    return total


def get_critical_path(graph: Any) -> Tuple[List[str], int]:
    nx = import_networkx()

    weighted = build_duration_weighted_graph(graph)
    raw_path = nx.dag_longest_path(
        weighted,
        weight="weight",
        topo_order=get_topological_order(weighted),
    )
    minutes = _path_weight(weighted, raw_path)
    path = [node_id for node_id in raw_path if node_id != _SOURCE_NODE_ID]

    return path, minutes


def get_upstream_operations(graph: Any, node_id: str) -> Set[str]:
    nx = import_networkx()
    return set(nx.ancestors(graph, node_id))


def get_downstream_operations(graph: Any, node_id: str) -> Set[str]:
    nx = import_networkx()
    return set(nx.descendants(graph, node_id))


def get_impact_count(graph: Any, node_id: str) -> int:
    return len(get_downstream_operations(graph, node_id))


def _build_downstream_critical_minutes_by_node(graph: Any) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for node_id in reversed(get_topological_order(graph)):
        result[node_id] = _duration_of(graph, node_id) + max(
            (int(data["lag_minutes"]) + result[to_node_id] for _from_node_id, to_node_id, data in graph.out_edges(node_id, data=True)),
            default=0,
        )
    return result


def get_downstream_critical_minutes(graph: Any, node_id: str) -> int:
    return _build_downstream_critical_minutes_by_node(graph)[node_id]


def build_node_metrics(graph: Any) -> Dict[str, Dict[str, Any]]:
    critical_path, _critical_minutes = get_critical_path(graph)
    critical_set = set(critical_path)
    critical_rank = {
        node_id: index
        for index, node_id in enumerate(critical_path)
    }
    generation_index = get_generation_index(graph)
    downstream_critical_minutes = _build_downstream_critical_minutes_by_node(graph)

    result: Dict[str, Dict[str, Any]] = {}

    for node_id in graph.nodes:
        result[node_id] = {
            "is_on_critical_path": node_id in critical_set,
            "critical_path_rank": critical_rank.get(node_id),
            "impact_count": get_impact_count(graph, node_id),
            "generation_index": generation_index[node_id],
            "downstream_critical_minutes": downstream_critical_minutes[node_id],
        }

    return result


__all__ = [
    "build_duration_weighted_graph",
    "build_node_metrics",
    "get_critical_path",
    "get_downstream_critical_minutes",
    "get_downstream_operations",
    "get_generation_index",
    "get_impact_count",
    "get_topological_generations",
    "get_topological_order",
    "get_upstream_operations",
]
