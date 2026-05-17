"""Scheduler graph analysis service orchestration.

This module must not import NetworkX at module import time.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .metrics import build_node_metrics, get_critical_path, get_topological_order
from .precedence_builder import build_linear_edges_by_batch, build_precedence_graph
from .types import GraphAnalysisSummary, GraphWarning, OperationGraphNode
from .validators import collect_graph_warnings, find_cycle_edges, is_dag


class ScheduleGraphAnalysisService:
    """工序图分析服务。"""

    def _build_graph_for_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ) -> object:
        node_list = list(nodes)
        edges = build_linear_edges_by_batch(node_list)
        return build_precedence_graph(node_list, edges)

    def analyze_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ) -> GraphAnalysisSummary:
        graph: Any = self._build_graph_for_linear_batches(nodes)

        cycle_edges = find_cycle_edges(graph)
        dag_ok = is_dag(graph)
        warnings = collect_graph_warnings(graph)

        topological_order = []
        critical_path = []
        critical_path_minutes = 0
        node_metrics: Dict[str, Dict[str, Any]] = {}

        if dag_ok:
            topological_order = get_topological_order(graph)
            critical_path, critical_path_minutes = get_critical_path(graph)
            node_metrics = build_node_metrics(graph)
        else:
            warnings.append(
                GraphWarning(
                    code="GRAPH_HAS_CYCLE",
                    message="工序依赖图存在循环，无法计算拓扑顺序和关键路径。",
                    data={"cycle_edges": cycle_edges},
                )
            )

        return GraphAnalysisSummary(
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            is_dag=dag_ok,
            cycle_edges=cycle_edges,
            topological_order=topological_order,
            critical_path=critical_path,
            critical_path_minutes=critical_path_minutes,
            node_metrics=node_metrics,
            warnings=warnings,
        )


__all__ = [
    "ScheduleGraphAnalysisService",
]
