from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from .nx_runtime import import_networkx
from .types import OperationGraphEdge, OperationGraphNode

_ALLOWED_EDGE_KINDS: Set[str] = {"precedence", "external_lag", "explicit"}


class GraphBuildContractError(ValueError):
    pass


def build_linear_edges_by_batch(nodes: Iterable[OperationGraphNode]) -> List[OperationGraphEdge]:
    grouped: Dict[str, List[OperationGraphNode]] = {}

    for node in nodes:
        _validate_node_object(node)
        grouped.setdefault(node.batch_id, []).append(node)

    edges: List[OperationGraphEdge] = []
    for batch_id, batch_nodes in grouped.items():
        ordered = sorted(batch_nodes, key=lambda item: (item.seq, item.op_code, item.node_id))
        for prev_node, next_node in zip(ordered, ordered[1:]):
            kind = "external_lag" if prev_node.source == "external" else "precedence"
            edges.append(
                OperationGraphEdge(
                    from_node_id=prev_node.node_id,
                    to_node_id=next_node.node_id,
                    kind=kind,
                    lag_minutes=0,
                    note=f"batch={batch_id} seq {prev_node.seq} -> {next_node.seq}",
                )
            )

    return edges


def build_precedence_graph(
    nodes: Iterable[OperationGraphNode],
    edges: Iterable[OperationGraphEdge],
) -> Any:
    node_list = list(nodes)
    edge_list = list(edges)

    _validate_node_objects(node_list)
    _validate_edge_objects(edge_list)
    _validate_unique_node_ids(node_list)

    node_ids = {node.node_id for node in node_list}
    for edge in edge_list:
        _validate_edge(edge, node_ids)

    nx = import_networkx()
    graph = nx.DiGraph()

    for node in node_list:
        graph.add_node(node.node_id, **_node_attrs(node))

    for edge in edge_list:
        graph.add_edge(edge.from_node_id, edge.to_node_id, **_edge_attrs(edge))

    return graph


def _validate_node_objects(nodes: List[OperationGraphNode]) -> None:
    for node in nodes:
        _validate_node_object(node)


def _validate_node_object(node: object) -> None:
    if not isinstance(node, OperationGraphNode):
        raise GraphBuildContractError("nodes 只能包含 OperationGraphNode。")


def _validate_edge_objects(edges: List[OperationGraphEdge]) -> None:
    for edge in edges:
        if not isinstance(edge, OperationGraphEdge):
            raise GraphBuildContractError("edges 只能包含 OperationGraphEdge。")


def _validate_unique_node_ids(nodes: List[OperationGraphNode]) -> None:
    seen: Dict[str, OperationGraphNode] = {}
    for node in nodes:
        previous = seen.get(node.node_id)
        if previous is not None:
            raise GraphBuildContractError(
                f"重复 node_id：{node.node_id}，样本 op_code：{previous.op_code} / {node.op_code}"
            )
        seen[node.node_id] = node


def _validate_edge(edge: OperationGraphEdge, node_ids: Set[str]) -> None:
    if not edge.from_node_id:
        raise GraphBuildContractError("edge.from_node_id 不能为空。")
    if not edge.to_node_id:
        raise GraphBuildContractError("edge.to_node_id 不能为空。")
    if edge.from_node_id not in node_ids:
        raise GraphBuildContractError(f"edge.from_node_id 不在节点集合里：{edge.from_node_id}")
    if edge.to_node_id not in node_ids:
        raise GraphBuildContractError(f"edge.to_node_id 不在节点集合里：{edge.to_node_id}")
    if edge.kind not in _ALLOWED_EDGE_KINDS:
        raise GraphBuildContractError(f"edge.kind 不支持：{edge.kind}")
    if edge.lag_minutes < 0:
        raise GraphBuildContractError("edge.lag_minutes 不能为负数。")


def _node_attrs(node: OperationGraphNode) -> Dict[str, Any]:
    return {
        "batch_id": node.batch_id,
        "op_code": node.op_code,
        "seq": node.seq,
        "name": node.name,
        "duration_minutes": node.duration_minutes,
        "part_no": node.part_no,
        "priority": node.priority,
        "source": node.source,
        "status": node.status,
        "due_date": node.due_date,
        "op_type_id": node.op_type_id,
        "machine_id": node.machine_id,
        "operator_id": node.operator_id,
        "supplier_id": node.supplier_id,
        "ext_group_id": node.ext_group_id,
        "ext_merge_mode": node.ext_merge_mode,
        "ext_group_total_days": node.ext_group_total_days,
        "merge_context_degraded": node.merge_context_degraded,
        "candidate_machine_ids": list(node.candidate_machine_ids),
        "candidate_operator_ids": list(node.candidate_operator_ids),
        "raw": dict(node.raw),
    }


def _edge_attrs(edge: OperationGraphEdge) -> Dict[str, Any]:
    return {
        "kind": edge.kind,
        "lag_minutes": edge.lag_minutes,
        "note": edge.note,
    }


__all__ = [
    "GraphBuildContractError",
    "build_linear_edges_by_batch",
    "build_precedence_graph",
]
