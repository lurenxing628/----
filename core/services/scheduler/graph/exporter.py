"""Scheduler graph export helpers.

This module must not import NetworkX at module import time.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from .types import GraphAnalysisSummary, GraphWarning


def _node_sort_key(item: Tuple[str, Dict[str, Any]]) -> Tuple[str, int, str, str]:
    node_id, data = item
    return (
        str(data["batch_id"]),
        int(data["seq"]),
        str(data["op_code"]),
        str(node_id),
    )


def _edge_sort_key(graph: Any, item: Tuple[str, str, Dict[str, Any]]) -> Tuple[str, int, str, str, str]:
    from_node_id, to_node_id, _data = item
    from_data = graph.nodes[from_node_id]
    return (
        str(from_data["batch_id"]),
        int(from_data["seq"]),
        str(from_data["op_code"]),
        str(from_node_id),
        str(to_node_id),
    )


def graph_to_plain_dict(graph: Any) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for node_id, data in sorted(graph.nodes(data=True), key=_node_sort_key):
        nodes.append(
            {
                "id": node_id,
                "batch_id": data["batch_id"],
                "op_code": data["op_code"],
                "seq": data["seq"],
                "duration_minutes": data["duration_minutes"],
            }
        )

    for from_node_id, to_node_id, data in sorted(graph.edges(data=True), key=lambda item: _edge_sort_key(graph, item)):
        edges.append(
            {
                "from": from_node_id,
                "to": to_node_id,
                "kind": data["kind"],
                "lag_minutes": data["lag_minutes"],
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
    }


def graph_warning_to_dict(warning: GraphWarning) -> Dict[str, Any]:
    return asdict(warning)


def graph_summary_to_dict(summary: GraphAnalysisSummary) -> Dict[str, Any]:
    return {
        "node_count": summary.node_count,
        "edge_count": summary.edge_count,
        "is_dag": summary.is_dag,
        "cycle_edges": summary.cycle_edges,
        "topological_order": summary.topological_order,
        "critical_path": summary.critical_path,
        "critical_path_minutes": summary.critical_path_minutes,
        "node_metrics": summary.node_metrics,
        "warnings": [graph_warning_to_dict(warning) for warning in summary.warnings],
    }


__all__ = [
    "graph_summary_to_dict",
    "graph_to_plain_dict",
    "graph_warning_to_dict",
]
