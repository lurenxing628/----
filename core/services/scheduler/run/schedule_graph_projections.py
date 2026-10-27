"""Build the graph projections owned by one search preparation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schedule_graph_dispatch_context import build_graph_ready_context, schedule_input_op_id_sets
from .schedule_graph_resource_matching_context import build_graph_resource_matching_projection
from .schedule_graph_score_projection import build_graph_score_projection


@dataclass(frozen=True)
class GraphDispatchProjections:
    ready_context: Optional[Dict[str, Any]]
    score_public: Dict[str, Any]
    score_diagnostics: Dict[str, Any]
    resource_matching_public: Dict[str, Any]
    resource_matching_diagnostics: Dict[str, Any]


def build_graph_dispatch_projections(
    schedule_input: Any,
    *,
    mode: str,
    nodes: List[Any],
    edges: List[Any],
    payload: Dict[str, Any],
    score_requested: bool,
    score_weights: Optional[Dict[str, int]],
) -> GraphDispatchProjections:
    is_dag = bool(payload["is_dag"])
    op_id_sets = schedule_input_op_id_sets(schedule_input) if is_dag else None
    score, score_public, score_diagnostics = build_graph_score_projection(
        mode=mode,
        is_dag=is_dag,
        score_requested=score_requested,
        score_weights=score_weights,
        nodes=nodes,
        node_metrics=payload["node_metrics"],
        topological_order=payload["topological_order"],
        schedule_input=schedule_input,
        op_id_sets=op_id_sets,
    )
    ready = build_graph_ready_context(
        schedule_input, nodes=nodes, edges=edges,
        enabled=(mode == "on" and is_dag),
        score_context=score,
        op_id_sets=op_id_sets,
    )
    resource_public, resource_diagnostics = build_graph_resource_matching_projection(
        mode=mode,
        is_dag=is_dag,
        schedule_input=schedule_input,
        nodes=nodes,
        edges=edges,
        graph_ready_context=ready,
        op_id_sets=op_id_sets,
    )
    return GraphDispatchProjections(
        ready, score_public, score_diagnostics, resource_public, resource_diagnostics,
    )
