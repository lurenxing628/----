from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .nx_runtime import import_networkx
from .types import GraphWarning


def _node_sort_key(graph: Any, node_id: str) -> Tuple[str, int, str, str]:
    data = graph.nodes[node_id]
    return (
        str(data["batch_id"]),
        int(data["seq"]),
        str(data["op_code"]),
        str(node_id),
    )


def is_dag(graph: Any) -> bool:
    nx = import_networkx()
    return bool(nx.is_directed_acyclic_graph(graph))


def find_cycle_edges(graph: Any) -> List[Dict[str, Any]]:
    nx = import_networkx()

    try:
        cycle = nx.find_cycle(graph, orientation="original")
    except nx.NetworkXNoCycle:
        return []

    result: List[Dict[str, Any]] = []
    for item in cycle:
        from_node_id = item[0]
        to_node_id = item[1]
        edge_data = graph.edges[from_node_id, to_node_id]
        result.append(
            {
                "from": from_node_id,
                "to": to_node_id,
                "from_op_code": graph.nodes[from_node_id]["op_code"],
                "to_op_code": graph.nodes[to_node_id]["op_code"],
                "kind": edge_data["kind"],
            }
        )
    return result


def find_isolated_nodes(graph: Any) -> List[str]:
    return [
        node_id
        for node_id in sorted(graph.nodes, key=lambda item: _node_sort_key(graph, item))
        if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0
    ]


def find_duplicate_seq_warnings(graph: Any) -> List[GraphWarning]:
    grouped: Dict[Tuple[str, int], List[str]] = {}

    for node_id, data in graph.nodes(data=True):
        batch_id = data["batch_id"]
        seq = data["seq"]
        key = (str(batch_id), int(seq))
        grouped.setdefault(key, []).append(node_id)

    warnings: List[GraphWarning] = []
    for key in sorted(grouped):
        batch_id, seq = key
        node_ids = sorted(grouped[key], key=lambda item: _node_sort_key(graph, item))
        if len(node_ids) <= 1:
            continue
        op_codes = [str(graph.nodes[node_id]["op_code"]) for node_id in node_ids]
        warnings.append(
            GraphWarning(
                code="DUPLICATE_SEQ",
                message=f"同一批次存在重复工序顺序号：batch_id={batch_id}, seq={seq}",
                data={
                    "batch_id": batch_id,
                    "seq": seq,
                    "node_ids": list(node_ids),
                    "op_codes": op_codes,
                },
            )
        )

    return warnings


def collect_graph_warnings(graph: Any) -> List[GraphWarning]:
    warnings: List[GraphWarning] = []

    for node_id in find_isolated_nodes(graph):
        data = graph.nodes[node_id]
        op_code = data["op_code"]
        warnings.append(
            GraphWarning(
                code="ISOLATED_OPERATION",
                message=f"发现孤立工序：{op_code}",
                data={
                    "node_id": node_id,
                    "op_code": op_code,
                    "batch_id": data["batch_id"],
                    "seq": data["seq"],
                },
            )
        )

    warnings.extend(find_duplicate_seq_warnings(graph))
    return warnings


__all__ = [
    "collect_graph_warnings",
    "find_cycle_edges",
    "find_duplicate_seq_warnings",
    "find_isolated_nodes",
    "is_dag",
]
