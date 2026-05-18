from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError

from .schedule_input_collector import ScheduleRunInput

_GRAPH_ANALYSIS_MODES = {"off", "report", "on"}
_GRAPH_TOPOLOGICAL_SAMPLE_LIMIT = 20
_GRAPH_CRITICAL_PATH_SAMPLE_LIMIT = 50
_GRAPH_WARNING_SAMPLE_LIMIT = 20
_GRAPH_CYCLE_EDGE_SAMPLE_LIMIT = 20
_GRAPH_NODE_METRIC_SAMPLE_LIMIT = 20
_GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT = 20
_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT = 20
_GRAPH_WARNING_TEXT_SAMPLE_LIMIT = 500
_GRAPH_INPUT_SCOPE = "all_algo_ops_with_frozen_markers"
_GRAPH_CYCLE_DISABLED_REASON = "schedule_graph_cycle"


@dataclass(frozen=True)
class ScheduleGraphDispatchPreparation:
    graph_analysis_public: Optional[Dict[str, Any]]
    graph_analysis_diagnostics: Optional[Dict[str, Any]]
    graph_ready_context: Optional[Any]
    graph_dispatch_mode_override: Optional[str] = None


def _elapsed_ms(started: float) -> int:
    return int((time.time() - float(started)) * 1000)


def _graph_analysis_mode(cfg: Any) -> str:
    mode = str(cfg.graph_analysis_mode).strip().lower()
    if mode not in _GRAPH_ANALYSIS_MODES:
        raise ValueError(f"graph_analysis_mode 只支持 off/report/on：{mode!r}")
    return mode


def _graph_block_on_cycle(cfg: Any) -> str:
    value = str(getattr(cfg, "graph_block_on_cycle", "no") or "no").strip().lower()
    if value not in ("yes", "no"):
        raise ValueError(f"graph_block_on_cycle 只支持 yes/no：{value!r}")
    return value


def maybe_analyze_schedule_graph(
    schedule_input: ScheduleRunInput,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    preparation = prepare_schedule_graph_for_dispatch(schedule_input)
    return preparation.graph_analysis_public, preparation.graph_analysis_diagnostics


def prepare_schedule_graph_for_dispatch(
    schedule_input: ScheduleRunInput,
) -> ScheduleGraphDispatchPreparation:
    mode = _graph_analysis_mode(schedule_input.cfg)
    if mode == "off":
        return ScheduleGraphDispatchPreparation(
            graph_analysis_public=None,
            graph_analysis_diagnostics=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )
    graph_block_on_cycle = _graph_block_on_cycle(schedule_input.cfg)
    public, diagnostics, graph_ready_context, graph_dispatch_mode_override = _build_schedule_graph_analysis_projection(
        schedule_input,
        mode=mode,
        graph_block_on_cycle=graph_block_on_cycle,
    )
    _enforce_graph_dispatch_policy(
        mode=mode,
        graph_block_on_cycle=graph_block_on_cycle,
        public=public,
        diagnostics=diagnostics,
    )
    return ScheduleGraphDispatchPreparation(
        graph_analysis_public=public,
        graph_analysis_diagnostics=diagnostics,
        graph_ready_context=graph_ready_context,
        graph_dispatch_mode_override=graph_dispatch_mode_override,
    )


def _build_schedule_graph_analysis_projection(
    schedule_input: ScheduleRunInput,
    *,
    mode: str,
    graph_block_on_cycle: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import GraphInputContractError, build_operation_nodes_from_rows
    from core.services.scheduler.graph.nx_runtime import NetworkXUnavailable
    from core.services.scheduler.graph.precedence_builder import GraphBuildContractError, build_linear_edges_by_batch

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
        edges = build_linear_edges_by_batch(nodes)
        summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes, metrics_mode="basic")
        payload = graph_summary_to_dict(summary)
        graph_ready_context = _build_graph_ready_context(
            schedule_input,
            nodes=nodes,
            edges=edges,
            enabled=(mode == "on" and bool(payload["is_dag"])),
        )
    except NetworkXUnavailable as exc:
        public, diagnostics = _graph_unavailable_projection(mode=mode, exc=exc, elapsed_ms=_elapsed_ms(started), scope=scope)
        return public, diagnostics, None, None
    except GraphInputContractError as exc:
        public, diagnostics = _graph_contract_error_projection(
            mode=mode,
            status="input_error",
            reason="graph_input_contract_error",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )
        return public, diagnostics, None, None
    except GraphBuildContractError as exc:
        public, diagnostics = _graph_contract_error_projection(
            mode=mode,
            status="build_error",
            reason="graph_build_contract_error",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )
        return public, diagnostics, None, None

    public, diagnostics = _project_graph_analysis_payload(
        mode=mode,
        graph_block_on_cycle=graph_block_on_cycle,
        payload=payload,
        elapsed_ms=_elapsed_ms(started),
        scope=scope,
    )
    return public, diagnostics, graph_ready_context, _graph_dispatch_mode_override(public)


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


def _node_op_id(node: Any) -> int:
    raw = getattr(node, "raw", {}) or {}
    value = raw.get("id") if isinstance(raw, dict) else None
    if isinstance(value, bool):
        value = None
    try:
        op_id = int(value or 0)
    except (TypeError, ValueError):
        op_id = 0
    if op_id <= 0:
        from core.services.scheduler.graph.input_adapter import GraphInputContractError

        raise GraphInputContractError(f"graph_ready_context 节点缺少有效 op_id：{getattr(node, 'node_id', '-')}")
    return op_id


def _positive_op_id_set(values: Any) -> Set[int]:
    result: Set[int] = set()
    for value in values or ():
        if isinstance(value, bool):
            continue
        try:
            op_id = int(value or 0)
        except (TypeError, ValueError):
            continue
        if op_id > 0:
            result.add(op_id)
    return result


def _sort_key_by_op_id(nodes: List[Any], *, schedulable_op_ids: Set[int]) -> Dict[int, Tuple[int, int, int]]:
    batch_order: Dict[str, int] = {}
    for node in sorted(nodes, key=lambda item: (str(item.batch_id), int(item.seq), str(item.op_code), str(item.node_id))):
        batch_order.setdefault(str(node.batch_id), len(batch_order))
    sort_keys: Dict[int, Tuple[int, int, int]] = {}
    for node in nodes:
        op_id = _node_op_id(node)
        if op_id in schedulable_op_ids:
            sort_keys[op_id] = (int(batch_order[str(node.batch_id)]), int(node.seq), int(op_id))
    return sort_keys


def _build_predecessor_successor_maps(nodes: List[Any], edges: List[Any]) -> Tuple[Dict[int, Set[int]], Dict[int, Set[int]]]:
    op_id_by_node_id = {str(node.node_id): _node_op_id(node) for node in nodes}
    predecessors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    successors: Dict[int, Set[int]] = {op_id: set() for op_id in op_id_by_node_id.values()}
    for edge in edges:
        from_op_id = op_id_by_node_id[str(edge.from_node_id)]
        to_op_id = op_id_by_node_id[str(edge.to_node_id)]
        predecessors.setdefault(to_op_id, set()).add(from_op_id)
        successors.setdefault(from_op_id, set()).add(to_op_id)
    return predecessors, successors


def _build_graph_ready_context(
    schedule_input: ScheduleRunInput,
    *,
    nodes: List[Any],
    edges: List[Any],
    enabled: bool,
) -> Optional[Dict[str, Any]]:
    if not enabled:
        return None
    schedulable_op_ids = _positive_op_id_set(getattr(op, "id", None) for op in schedule_input.algo_ops_to_schedule or [])
    fixed_op_ids = _positive_op_id_set(schedule_input.frozen_op_ids or ())
    fixed_op_ids.update(_positive_op_id_set((item or {}).get("op_id") if isinstance(item, dict) else getattr(item, "op_id", None) for item in schedule_input.seed_results or ()))
    predecessor_map, successor_map = _build_predecessor_successor_maps(nodes, edges)
    return {
        "enabled": True,
        "disabled_reason": None,
        "schedulable_op_ids": set(schedulable_op_ids),
        "fixed_op_ids": set(fixed_op_ids),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": _sort_key_by_op_id(nodes, schedulable_op_ids=schedulable_op_ids),
    }


def _effective_graph_analysis_mode(mode: str) -> str:
    if mode == "on":
        return "report_only"
    return mode


def _graph_cycle_disabled_public_fields() -> Dict[str, Any]:
    return {
        "effective_mode": "sgs_without_graph_ready_queue",
        "graph_enhancement_allowed": False,
        "graph_enhancement_disabled_reason": _GRAPH_CYCLE_DISABLED_REASON,
        "ready_queue_enabled": False,
        "graph_enhancement_message": "工序图存在循环，本次跳过图 ready 队列，继续使用原 SGS 候选逻辑。",
    }


def _graph_dispatch_mode_override(public: Dict[str, Any]) -> Optional[str]:
    if public.get("effective_mode") == "sgs_without_graph_ready_queue":
        return "sgs"
    return None


def _graph_ready_public_fields(*, mode: str, is_dag: bool, graph_block_on_cycle: str) -> Dict[str, Any]:
    if mode != "on":
        return {}
    if is_dag:
        return {
            "effective_mode": "graph_ready_queue",
            "graph_enhancement_allowed": True,
            "graph_enhancement_disabled_reason": None,
            "ready_queue_enabled": True,
        }
    if graph_block_on_cycle == "no":
        return _graph_cycle_disabled_public_fields()
    return {
        "graph_enhancement_allowed": False,
        "graph_enhancement_disabled_reason": _GRAPH_CYCLE_DISABLED_REASON,
        "ready_queue_enabled": False,
    }


def _format_cycle_error_message(diagnostics: Optional[Dict[str, Any]]) -> str:
    sample = []
    if isinstance(diagnostics, dict):
        sample = list(diagnostics.get("cycle_edges_sample") or [])
    if not sample:
        return "工序图存在循环依赖，已按配置停止排产。请先检查工艺路线里的前后工序关系。"
    return f"工序图存在循环依赖，已按配置停止排产。请先检查这些环边样本：{sample}"


def _cycle_error_details(diagnostics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    sample = []
    count = 0
    if isinstance(diagnostics, dict):
        sample = list(diagnostics.get("cycle_edges_sample") or [])
        count = int(diagnostics.get("cycle_edge_count") or len(sample))
    return {
        "reason": _GRAPH_CYCLE_DISABLED_REASON,
        "cycle_edge_count": int(count),
        "cycle_edges_sample": sample,
    }


def _enforce_graph_dispatch_policy(
    *,
    mode: str,
    graph_block_on_cycle: str,
    public: Dict[str, Any],
    diagnostics: Optional[Dict[str, Any]],
) -> None:
    if mode != "on":
        return
    status = str(public.get("status") or "")
    if status != "available":
        reason = str(public.get("reason") or "graph_enhancement_unavailable")
        message = str(public.get("message") or "工序图增强无法启用。")
        raise ValidationError(
            f"工序图增强无法启用：{message}",
            field=reason,
            details={"reason": reason, "status": status},
        )
    if bool(public.get("is_dag", False)):
        return
    if graph_block_on_cycle == "yes":
        raise ValidationError(
            _format_cycle_error_message(diagnostics),
            field=_GRAPH_CYCLE_DISABLED_REASON,
            details=_cycle_error_details(diagnostics),
        )


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
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    if isinstance(value, str):
        if len(value) <= _GRAPH_WARNING_TEXT_SAMPLE_LIMIT:
            return value, False
        return {
            "text_sample": value[:_GRAPH_WARNING_TEXT_SAMPLE_LIMIT],
            "text_length": int(len(value)),
            "text_truncated": True,
        }, True
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


def _project_warning_message(message: Any) -> Tuple[str, bool]:
    text = str(message or "")
    if len(text) <= _GRAPH_WARNING_TEXT_SAMPLE_LIMIT:
        return text, False
    return text[:_GRAPH_WARNING_TEXT_SAMPLE_LIMIT], True


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
    message, message_truncated = _project_warning_message(warning["message"])
    return {
        "code": warning["code"],
        "message": message,
        "message_length": len(str(warning["message"] or "")),
        "message_truncated": bool(message_truncated),
        "data": data,
        "warning_data_truncated": bool(warning_data_truncated or message_truncated),
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
    graph_block_on_cycle: str = "no",
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
    public.update(
        _graph_ready_public_fields(
            mode=mode,
            is_dag=bool(payload["is_dag"]),
            graph_block_on_cycle=graph_block_on_cycle,
        )
    )
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


__all__ = [
    "ScheduleGraphDispatchPreparation",
    "maybe_analyze_schedule_graph",
    "prepare_schedule_graph_for_dispatch",
]
