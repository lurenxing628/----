"""Build the graph projections owned by one search preparation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schedule_graph_dispatch_context import (
    build_graph_health_context,
    build_graph_ready_context,
    build_graph_resource_matching_projection,
)
from .schedule_graph_score_projection import build_graph_score_projection


@dataclass(frozen=True)
class GraphDispatchProjections:
    health_context: Dict[str, Any]
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
    health = build_graph_health_context(
        nodes=nodes, payload=payload, schedule_input=schedule_input,
    )
    score, score_public, score_diagnostics = build_graph_score_projection(
        mode=mode,
        is_dag=bool(payload["is_dag"]),
        score_requested=score_requested,
        score_weights=score_weights,
        nodes=nodes,
        node_metrics=dict(payload["node_metrics"]),
        topological_order=list(payload["topological_order"]),
        schedule_input=schedule_input,
    )
    ready = build_graph_ready_context(
        schedule_input, nodes=nodes, edges=edges,
        enabled=(mode == "on" and bool(payload["is_dag"])),
    )
    resource_public, resource_diagnostics = build_graph_resource_matching_projection(
        mode=mode,
        is_dag=bool(payload["is_dag"]),
        graph_enhancement_allowed=bool(mode != "on" or ready is not None),
        graph_enhancement_disabled_reason=None,
        schedule_input=schedule_input,
        nodes=nodes,
        edges=edges,
        graph_ready_context=ready,
    )
    if ready is not None and score:
        ready.update(score)
    return GraphDispatchProjections(
        health, ready, score_public, score_diagnostics, resource_public, resource_diagnostics,
    )
