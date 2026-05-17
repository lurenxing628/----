from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .schedule_input_collector import ScheduleRunInput

_GRAPH_ANALYSIS_MODES = {"off", "report", "on"}
_GRAPH_TOPOLOGICAL_SAMPLE_LIMIT = 20
_GRAPH_CRITICAL_PATH_SAMPLE_LIMIT = 50
_GRAPH_WARNING_SAMPLE_LIMIT = 20
_GRAPH_CYCLE_EDGE_SAMPLE_LIMIT = 20
_GRAPH_NODE_METRIC_SAMPLE_LIMIT = 20
_GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT = 20
_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT = 20
_GRAPH_INPUT_SCOPE = "all_algo_ops_with_frozen_markers"
_JSON_SCALAR_TYPES = (str, int, float, bool)


def _elapsed_ms(started: float) -> int:
    return int((time.time() - float(started)) * 1000)


def _graph_analysis_mode(cfg: Any) -> str:
    mode = str(cfg.graph_analysis_mode).strip().lower()
    if mode not in _GRAPH_ANALYSIS_MODES:
        raise ValueError(f"graph_analysis_mode 只支持 off/report/on：{mode!r}")
    return mode


def maybe_analyze_schedule_graph(
    schedule_input: ScheduleRunInput,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    mode = _graph_analysis_mode(schedule_input.cfg)
    if mode == "off":
        return None, None
    return _build_schedule_graph_analysis_projection(schedule_input, mode=mode)


def _build_schedule_graph_analysis_projection(
    schedule_input: ScheduleRunInput,
    *,
    mode: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import GraphInputContractError, build_operation_nodes_from_rows
    from core.services.scheduler.graph.nx_runtime import NetworkXUnavailable
    from core.services.scheduler.graph.precedence_builder import GraphBuildContractError

    started = time.time()
    scope = _graph_input_scope(schedule_input)
    try:
        nodes = build_operation_nodes_from_rows(
            schedule_input.algo_ops,
            batches=schedule_input.batches,
            resource_pool=schedule_input.resource_pool,
            frozen_op_ids=schedule_input.frozen_op_ids,
        )
        scope = _graph_input_scope(schedule_input, nodes=nodes)
        summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes, metrics_mode="basic")
        payload = graph_summary_to_dict(summary)
    except NetworkXUnavailable as exc:
        return _graph_unavailable_projection(mode=mode, exc=exc, elapsed_ms=_elapsed_ms(started), scope=scope)
    except GraphInputContractError as exc:
        return _graph_contract_error_projection(
            mode=mode,
            status="input_error",
            reason="graph_input_contract_error",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )
    except GraphBuildContractError as exc:
        return _graph_contract_error_projection(
            mode=mode,
            status="build_error",
            reason="graph_build_contract_error",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )

    return _project_graph_analysis_payload(
        mode=mode,
        payload=payload,
        elapsed_ms=_elapsed_ms(started),
        scope=scope,
    )


def _graph_input_scope(schedule_input: ScheduleRunInput, *, nodes: Optional[List[Any]] = None) -> Dict[str, Any]:
    if nodes is None:
        frozen_node_count = len(schedule_input.frozen_op_ids or set())
    else:
        frozen_node_count = sum(1 for node in nodes if bool(node.is_frozen))
    return {
        "input_scope": _GRAPH_INPUT_SCOPE,
        "total_algo_op_count": int(len(schedule_input.algo_ops or [])),
        "reschedulable_unfrozen_op_count": int(len(schedule_input.algo_ops_to_schedule or [])),
        "frozen_node_count": int(frozen_node_count),
        "seed_result_count": int(len(schedule_input.seed_results or [])),
    }


def _effective_graph_analysis_mode(mode: str) -> str:
    if mode == "on":
        return "report_only"
    return mode


def _graph_unavailable_projection(
    *,
    mode: str,
    exc: Exception,
    elapsed_ms: int,
    scope: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    return (
        {
            "mode": mode,
            "effective_mode": _effective_graph_analysis_mode(mode),
            "status": "unavailable",
            "reason": "networkx_unavailable",
            "message": str(exc),
            "time_cost_ms": int(elapsed_ms),
            **dict(scope),
        },
        None,
    )


def _graph_contract_error_projection(
    *,
    mode: str,
    status: str,
    reason: str,
    exc: Exception,
    elapsed_ms: int,
    scope: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    return (
        {
            "mode": mode,
            "effective_mode": _effective_graph_analysis_mode(mode),
            "status": status,
            "reason": reason,
            "message": str(exc),
            "time_cost_ms": int(elapsed_ms),
            **dict(scope),
        },
        None,
    )


def _truncated(values: List[Any], limit: int) -> bool:
    return len(values) > int(limit)


def _sample(values: List[Any], limit: int) -> List[Any]:
    return list(values[: int(limit)])


def _project_warning_data_value(value: Any) -> Tuple[Any, bool]:
    if value is None or isinstance(value, _JSON_SCALAR_TYPES):
        return value, False
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        projected_items: List[Any] = []
        truncated_any = _truncated(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT)
        for item in _sample(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT):
            projected_item, item_truncated = _project_warning_data_value(item)
            projected_items.append(projected_item)
            truncated_any = truncated_any or item_truncated
        return projected_items, truncated_any
    if isinstance(value, dict):
        items = list(value.items())
        projected: Dict[str, Any] = {}
        truncated_any = _truncated(items, _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT)
        for raw_key, raw_value in items[:_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT]:
            projected_value, value_truncated = _project_warning_data_value(raw_value)
            projected[str(raw_key)] = projected_value
            truncated_any = truncated_any or value_truncated
        if len(items) > _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT:
            projected["_field_count"] = int(len(items))
            projected["_fields_truncated"] = True
        return projected, truncated_any
    return {"unsupported_value_type": type(value).__name__}, True


def _project_warning_data(raw_data: Any) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(raw_data, dict):
        return {"unsupported_data_type": type(raw_data).__name__}, True
    projected: Dict[str, Any] = {}
    items = list(raw_data.items())
    truncated_any = _truncated(items, _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT)
    for key, value in items[:_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT]:
        key_text = str(key)
        if isinstance(value, list):
            sample, sample_truncated = _project_warning_data_value(value)
            projected[f"{key_text}_sample"] = sample
            projected[f"{key_text}_count"] = int(len(value))
            truncated = _truncated(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT)
            projected[f"{key_text}_truncated"] = bool(truncated or sample_truncated)
            truncated_any = truncated_any or truncated or sample_truncated
        else:
            projected_value, value_truncated = _project_warning_data_value(value)
            projected[key_text] = projected_value
            truncated_any = truncated_any or value_truncated
    if len(items) > _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT:
        projected["_field_count"] = int(len(items))
        projected["_fields_truncated"] = True
    return projected, truncated_any


def _project_warning(warning: Dict[str, Any]) -> Dict[str, Any]:
    data, warning_data_truncated = _project_warning_data(warning.get("data"))
    return {
        "code": warning["code"],
        "message": warning["message"],
        "data": data,
        "warning_data_truncated": bool(warning_data_truncated),
    }


def _node_metrics_sample(
    *,
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
) -> List[Dict[str, Any]]:
    if topological_order:
        sample_node_ids = topological_order[:_GRAPH_NODE_METRIC_SAMPLE_LIMIT]
    else:
        sample_node_ids = sorted(node_metrics)[:_GRAPH_NODE_METRIC_SAMPLE_LIMIT]
    return [
        {
            "node_id": node_id,
            "is_on_critical_path": bool(node_metrics[node_id]["is_on_critical_path"]),
            "critical_path_rank": node_metrics[node_id]["critical_path_rank"],
            "impact_count": int(node_metrics[node_id]["impact_count"]),
            "generation_index": int(node_metrics[node_id]["generation_index"]),
            "downstream_critical_minutes": int(node_metrics[node_id]["downstream_critical_minutes"]),
        }
        for node_id in sample_node_ids
        if node_id in node_metrics
    ]


def _project_graph_analysis_payload(
    *,
    mode: str,
    payload: Dict[str, Any],
    elapsed_ms: int,
    scope: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cycle_edges = list(payload["cycle_edges"])
    topological_order = list(payload["topological_order"])
    critical_path = list(payload["critical_path"])
    warnings = list(payload["warnings"])
    node_metrics = dict(payload["node_metrics"])

    public = {
        "mode": mode,
        "effective_mode": _effective_graph_analysis_mode(mode),
        "status": "available",
        "node_count": int(payload["node_count"]),
        "edge_count": int(payload["edge_count"]),
        "is_dag": bool(payload["is_dag"]),
        "critical_path_minutes": int(payload["critical_path_minutes"]),
        "critical_path_node_count": int(len(critical_path)),
        "warning_count": int(len(warnings)),
        "cycle_edge_count": int(len(cycle_edges)),
        "time_cost_ms": int(elapsed_ms),
        **dict(scope),
    }
    diagnostics = {
        "topological_order_sample": _sample(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "topological_order_count": int(len(topological_order)),
        "topological_order_truncated": _truncated(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "critical_path_sample": _sample(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "critical_path_count": int(len(critical_path)),
        "critical_path_truncated": _truncated(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "cycle_edges_sample": _sample(cycle_edges, _GRAPH_CYCLE_EDGE_SAMPLE_LIMIT),
        "cycle_edge_count": int(len(cycle_edges)),
        "warnings_sample": [_project_warning(warning) for warning in warnings[:_GRAPH_WARNING_SAMPLE_LIMIT]],
        "warning_count": int(len(warnings)),
        "node_metrics_sample": _node_metrics_sample(
            node_metrics=node_metrics,
            topological_order=topological_order,
        ),
        "node_metrics_count": int(len(node_metrics)),
        "node_metrics_truncated": _truncated(
            list(node_metrics),
            _GRAPH_NODE_METRIC_SAMPLE_LIMIT,
        ),
        "node_metrics_status": "available" if node_metrics else "skipped_basic_report",
    }
    return public, diagnostics


__all__ = ["maybe_analyze_schedule_graph"]
