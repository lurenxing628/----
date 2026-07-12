from __future__ import annotations

from typing import Any, Dict

from core.models.public_identifier_redaction import is_forbidden_internal_key, redact_internal_text

PUBLIC_GRAPH_ANALYSIS_KEYS = (
    "mode",
    "effective_mode",
    "status",
    "reason",
    "message",
    "node_count",
    "edge_count",
    "is_dag",
    "critical_path_minutes",
    "critical_path_node_count",
    "warning_count",
    "cycle_edge_count",
    "time_cost_ms",
    "input_scope",
    "total_algo_op_count",
    "reschedulable_unfrozen_op_count",
    "frozen_node_count",
    "seed_result_count",
    "graph_enhancement_allowed",
    "graph_enhancement_disabled_reason",
    "graph_enhancement_message",
    "ready_queue_enabled",
    "score_enabled",
    "score_metric_status",
    "score_disabled_reason",
    "score_weight_summary",
)

PUBLIC_RESOURCE_MATCHING_KEYS = (
    "status",
    "reason",
    "ready_operation_count",
    "operation_with_candidate_count",
    "machine_count",
    "edge_count",
    "matched_operation_count",
    "unmatched_operation_count",
    "bottleneck_machine_count",
)


def _project_public_graph_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _project_public_graph_dict(value)
    if isinstance(value, (list, tuple)):
        return _project_public_graph_sequence(value)
    if isinstance(value, str):
        return redact_internal_text(value)
    return value


def _project_public_graph_dict(value: Dict[Any, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, child in value.items():
        key_text = str(key or "").strip()
        if not is_forbidden_internal_key(key_text):
            out[key_text] = _project_public_graph_value(child)
    return out


def _project_public_graph_sequence(value: Any) -> Any:
    return [_project_public_graph_value(item) for item in value]


def project_public_graph_analysis(value: Any) -> Dict[str, Any]:
    """Return the graph-analysis payload allowed in public summaries and logs."""
    if not isinstance(value, dict):
        return {}
    out = {key: _project_public_graph_value(value[key]) for key in PUBLIC_GRAPH_ANALYSIS_KEYS if key in value}
    resource_matching = project_public_resource_matching(value.get("resource_matching"))
    if resource_matching:
        out["resource_matching"] = resource_matching
    return out


def project_public_resource_matching(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: _project_public_graph_value(value[key]) for key in PUBLIC_RESOURCE_MATCHING_KEYS if key in value}


__all__ = [
    "PUBLIC_GRAPH_ANALYSIS_KEYS",
    "PUBLIC_RESOURCE_MATCHING_KEYS",
    "project_public_graph_analysis",
    "project_public_resource_matching",
]
