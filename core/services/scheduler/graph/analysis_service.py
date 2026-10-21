"""Scheduler graph analysis service orchestration.

This module must not import NetworkX at module import time.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .metrics import build_node_metrics, get_critical_path, get_topological_generations
from .nx_runtime import import_networkx
from .precedence_builder import build_precedence_graph
from .types import GraphAnalysisSummary, GraphWarning, OperationGraphEdge, OperationGraphNode
from .validators import collect_graph_warnings, find_cycle_edges


class ScheduleGraphAnalysisService:
    """工序图分析服务。"""

    def analyze_precedence(
        self, nodes: Iterable[OperationGraphNode], edges: Iterable[OperationGraphEdge], *, metrics_mode: str = "full",
    ) -> GraphAnalysisSummary:
        """Analyze the same edges the dispatcher will consume."""
        if metrics_mode not in ("basic", "full"):
            raise ValueError(f"metrics_mode 只支持 basic/full：{metrics_mode!r}")
        return self._analyze_graph(build_precedence_graph(nodes, edges), metrics_mode=metrics_mode)

    def _analyze_graph(self, graph: Any, *, metrics_mode: str) -> GraphAnalysisSummary:
        nx = import_networkx()
        cycle_edges = []
        topological_generations = []
        try:
            topological_generations = get_topological_generations(graph)
        except nx.NetworkXUnfeasible:
            dag_ok = False
            cycle_edges = find_cycle_edges(graph)
        else:
            dag_ok = True
        warnings = collect_graph_warnings(graph)

        topological_order = []
        critical_path = []
        critical_path_minutes = 0
        node_metrics: Dict[str, Dict[str, Any]] = {}

        if dag_ok:
            topological_order = [
                node_id
                for group in topological_generations
                for node_id in group
            ]
            generation_index = {
                node_id: index
                for index, group in enumerate(topological_generations)
                for node_id in group
            }
            critical_path, critical_path_minutes = get_critical_path(
                graph, topological_order=topological_order,
            )
            if metrics_mode == "full":
                node_metrics = build_node_metrics(
                    graph,
                    topological_order=topological_order,
                    critical_path=critical_path,
                    generation_index=generation_index,
                )
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
