"""精确计算 DAG 后继数量，避免独立工序链使用全图宽度的位集合。"""

from __future__ import annotations

from typing import Any, Dict, List

from .nx_runtime import import_networkx


def compute_impact_counts_by_node(graph: Any, topological_order: List[str]) -> Dict[str, int]:
    """复用调用方的拓扑顺序；缺失或尚未计算的后继保持显式报错。"""
    if all(degree <= 1 for _node_id, degree in graph.out_degree()):
        return _compute_single_successor_counts(graph, topological_order)

    result: Dict[str, int] = {}
    for component_order in _component_topological_orders(graph, topological_order):
        result.update(_compute_component_impact_counts(graph, component_order))
    return result


def _compute_single_successor_counts(graph: Any, topological_order: List[str]) -> Dict[str, int]:
    # 无分叉时每个节点只有一条后继路径；允许多条路径汇入同一后继。
    result: Dict[str, int] = {}
    for node_id in reversed(topological_order):
        count = 0
        for successor_id in graph.successors(node_id):
            count = 1 + result[successor_id]
        result[node_id] = count
    return result


def _component_topological_orders(graph: Any, topological_order: List[str]) -> List[List[str]]:
    nx = import_networkx()
    component_by_node: Dict[str, int] = {}
    orders: List[List[str]] = []
    for component_id, component_nodes in enumerate(nx.weakly_connected_components(graph)):
        orders.append([])
        for node_id in component_nodes:
            component_by_node[node_id] = component_id

    # 一次分组，避免每个分量重新扫描全图拓扑序；batch_id 不代表真实连通性。
    for node_id in topological_order:
        orders[component_by_node[node_id]].append(node_id)
    return orders


def _compute_component_impact_counts(graph: Any, topological_order: List[str]) -> Dict[str, int]:
    node_to_index = {
        node_id: index
        for index, node_id in enumerate(topological_order)
    }
    downstream_bits_by_node: Dict[str, int] = {}
    result: Dict[str, int] = {}
    for node_id in reversed(topological_order):
        mask = 0
        for successor_id in graph.successors(node_id):
            mask |= 1 << node_to_index[successor_id]
            mask |= downstream_bits_by_node[successor_id]
        downstream_bits_by_node[node_id] = mask
        result[node_id] = _popcount(mask)
    return result


def _popcount(mask: int) -> int:
    # Python 3.8 没有 int.bit_count()。
    return bin(mask).count("1")
