"""Reuse comparison-local graph projections while isolating candidate state."""
from __future__ import annotations

from copy import deepcopy
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


def copy_graph_ready_context(context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Copy a weight-independent ready template, including every mutable value."""
    if context is None:
        return None
    result = dict(context)
    for field in ("schedulable_op_ids", "fixed_op_ids"):
        result[field] = set(context[field])
    for field in ("predecessor_op_ids_by_op_id", "successor_op_ids_by_op_id"):
        result[field] = {op_id: set(op_ids) for op_id, op_ids in context[field].items()}
    for field in ("sort_key_by_op_id", "fixed_op_sources_by_op_id"):
        result[field] = dict(context[field])
    return result


def build_graph_dispatch_projections(
    schedule_input: Any,
    *,
    mode: str,
    metrics_mode: str,
    nodes: List[Any],
    edges: List[Any],
    payload: Dict[str, Any],
    score_requested: bool,
    score_weights: Optional[Dict[str, int]],
    core_cache: Optional[Dict[str, Any]],
) -> GraphDispatchProjections:
    # The comparison factory owns this cache; candidates replace cfg only.
    # Mode is part of the key because report and unscored on both use basic metrics.
    cache_key = "projection:" + metrics_mode + ":" + mode
    cached = core_cache.get(cache_key) if core_cache is not None else None
    health = deepcopy(cached["health"]) if cached is not None else build_graph_health_context(
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
    ready = copy_graph_ready_context(cached["ready"]) if cached is not None else build_graph_ready_context(
        schedule_input, nodes=nodes, edges=edges,
        enabled=(mode == "on" and bool(payload["is_dag"])),
    )
    if cached is not None:
        resource_public, resource_diagnostics = deepcopy(cached["resource_matching"])
    else:
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
        if core_cache is not None and resource_public.get("status") != "error":
            # Cache private copies before adding per-candidate scores or returning state.
            core_cache[cache_key] = {
                "health": deepcopy(health),
                "ready": copy_graph_ready_context(ready),
                "resource_matching": deepcopy((resource_public, resource_diagnostics)),
            }
    if ready is not None and score:
        ready.update(score)
    return GraphDispatchProjections(
        health, ready, score_public, score_diagnostics, resource_public, resource_diagnostics,
    )
