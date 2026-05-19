"""Scheduler graph analysis service orchestration.

This module must not import NetworkX at module import time.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .metrics import build_node_metrics, get_critical_path, get_topological_generations
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
        *,
        metrics_mode: str = "full",
    ) -> GraphAnalysisSummary:
        if metrics_mode not in ("basic", "full"):
            raise ValueError(f"metrics_mode 只支持 basic/full：{metrics_mode!r}")
        graph: Any = self._build_graph_for_linear_batches(nodes)

        cycle_edges = find_cycle_edges(graph)
        dag_ok = is_dag(graph)
        warnings = collect_graph_warnings(graph)

        topological_order = []
        critical_path = []
        critical_path_minutes = 0
        node_metrics: Dict[str, Dict[str, Any]] = {}

        if dag_ok:
            topological_generations = get_topological_generations(graph)
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
            critical_path, critical_path_minutes = get_critical_path(graph)
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
