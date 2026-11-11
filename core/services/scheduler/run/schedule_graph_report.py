from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, cast

from core.errors import ValidationError

from .schedule_graph_dispatch_context import (
    GRAPH_CYCLE_DISABLED_REASON as _GRAPH_CYCLE_DISABLED_REASON,
)
from .schedule_graph_dispatch_context import (
    build_graph_ready_context as _build_graph_ready_context,
)
from .schedule_graph_dispatch_context import (
    effective_graph_analysis_mode as _effective_graph_analysis_mode,
)
from .schedule_graph_dispatch_context import (
    graph_dispatch_mode_override as _graph_dispatch_mode_override,
)
from .schedule_graph_dispatch_context import (
    graph_input_scope as _graph_input_scope,
)
from .schedule_graph_dispatch_context import (
    graph_ready_public_fields as _graph_ready_public_fields,
)
from .schedule_graph_dispatch_context import (
    schedule_input_op_id_sets as _schedule_input_op_id_sets,
)
from .schedule_graph_projection_helpers import (
    graph_node_metrics_sample as _graph_node_metrics_sample,
)
from .schedule_graph_projection_helpers import (
    is_truncated,
    sample_values,
)
from .schedule_graph_projection_helpers import (
    project_graph_warning as _project_graph_warning,
)
from .schedule_graph_projections import build_graph_dispatch_projections
from .schedule_graph_score_projection import (
    build_graph_score_projection as _build_graph_score_projection,
)
from .schedule_graph_score_projection import (
    graph_score_requested as _graph_score_requested,
)
from .schedule_graph_score_projection import (
    graph_score_weights as _graph_score_weights,
)
from .schedule_input_contracts import SolverInput

_GRAPH_TOPOLOGICAL_SAMPLE_LIMIT = 20
_GRAPH_CRITICAL_PATH_SAMPLE_LIMIT = 50
_GRAPH_WARNING_SAMPLE_LIMIT = 20
_GRAPH_CYCLE_EDGE_SAMPLE_LIMIT = 20
_GRAPH_NODE_METRIC_SAMPLE_LIMIT = 20


@dataclass(frozen=True)
class ScheduleGraphDispatchPreparation:
    graph_analysis_public: Optional[Dict[str, Any]]
    graph_analysis_diagnostics: Optional[Dict[str, Any]]
    graph_ready_context: Optional[Any]
    graph_dispatch_mode_override: Optional[str] = None


def _elapsed_ms(started: float) -> int:
    return max(int((time.monotonic() - float(started)) * 1000), 0)


def _prepare_piece_graph_for_dispatch(
    schedule_input: SolverInput,
    predecessors: Mapping[int, Sequence[int]],
    *,
    resource_pool: Optional[Mapping[str, Any]],
) -> ScheduleGraphDispatchPreparation:
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import (
        GraphResourcePreparation,
        build_operation_nodes_from_rows,
    )
    from core.services.scheduler.graph.metrics import (
        build_node_metrics,
        get_critical_path,
        get_topological_generations,
    )
    from core.services.scheduler.graph.precedence_builder import build_precedence_graph
    from core.services.scheduler.graph.types import GraphAnalysisSummary, OperationGraphEdge
    from core.services.scheduler.graph.validators import collect_graph_warnings

    weights = _graph_score_weights(schedule_input.config)
    score_requested = _graph_score_requested(weights)
    resources = GraphResourcePreparation(resource_pool)
    nodes = build_operation_nodes_from_rows(
        schedule_input.algo_ops,
        batches=schedule_input.batches,
        resource_preparation=resources,
        frozen_op_ids=schedule_input.seeds.frozen_op_ids,
    )
    by_id = {node.raw["id"]: node.node_id for node in nodes}
    edges = [
        OperationGraphEdge(by_id[previous], by_id[op_id], "precedence")
        for op_id, prev_ids in predecessors.items()
        if op_id in by_id
        for previous in prev_ids
        if previous in by_id
    ]
    graph = build_precedence_graph(nodes, edges)
    generations = get_topological_generations(graph)
    order = [key for group in generations for key in group]
    critical, minutes = get_critical_path(graph, topological_order=order)
    metrics = (
        build_node_metrics(
            graph,
            topological_order=order,
            critical_path=critical,
            generation_index={key: index for index, group in enumerate(generations) for key in group},
        )
        if score_requested
        else {}
    )
    payload = graph_summary_to_dict(
        GraphAnalysisSummary(
            len(nodes),
            len(edges),
            True,
            [],
            order,
            critical,
            minutes,
            metrics,
            collect_graph_warnings(graph),
        )
    )
    op_id_sets = _schedule_input_op_id_sets(schedule_input)
    schedulable_op_ids, _fixed_op_ids = op_id_sets
    score, score_public, score_diagnostics = _build_graph_score_projection(
        mode="on",
        is_dag=True,
        score_requested=score_requested,
        score_weights=weights,
        nodes=nodes,
        node_metrics=metrics,
        topological_order=order,
        schedulable_op_ids=schedulable_op_ids,
    )
    context: Any = _build_graph_ready_context(
        nodes=nodes,
        edges=edges,
        enabled=True,
        score_context=score,
        op_id_sets=op_id_sets,
    )
    context["piece_scope"] = True
    public, diagnostics = _project_graph_analysis_payload(
        mode="on",
        payload=payload,
        elapsed_ms=0,
        scope=_graph_input_scope(schedule_input, nodes=nodes),
        score_public=score_public,
        score_diagnostics=score_diagnostics,
    )
    return ScheduleGraphDispatchPreparation(public, diagnostics, context, "sgs")


def prepare_schedule_graph_for_dispatch(
    schedule_input: SolverInput,
    *,
    resource_pool: Optional[Mapping[str, Any]] = None,
) -> ScheduleGraphDispatchPreparation:
    """为本次搜索构建一次图分析、派工和资源投影。"""
    predecessors = schedule_input.predecessors
    if predecessors:
        return _prepare_piece_graph_for_dispatch(
            schedule_input,
            predecessors,
            resource_pool=resource_pool,
        )
    mode = schedule_input.config.graph_analysis_mode
    if mode == "off":
        return ScheduleGraphDispatchPreparation(
            graph_analysis_public=None,
            graph_analysis_diagnostics=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )
    graph_block_on_cycle = schedule_input.config.graph_block_on_cycle
    public, diagnostics, graph_ready_context, graph_dispatch_mode_override = _build_schedule_graph_analysis_projection(
        schedule_input,
        mode=mode,
        graph_block_on_cycle=graph_block_on_cycle,
        resource_pool=resource_pool,
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
    schedule_input: SolverInput,
    *,
    mode: str,
    graph_block_on_cycle: str,
    resource_pool: Optional[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
    from core.services.scheduler.graph.nx_runtime import NetworkXUnavailable
    from core.services.scheduler.graph.precedence_builder import GraphBuildContractError, build_linear_edges_by_batch

    started = time.monotonic()
    score_weights = _graph_score_weights(schedule_input.config)
    score_requested = mode == "on" and _graph_score_requested(score_weights)
    metrics_mode = "full" if score_requested else "basic"
    nodes = build_operation_nodes_from_rows(
        schedule_input.algo_ops,
        batches=schedule_input.batches,
        resource_pool=resource_pool,
        frozen_op_ids=schedule_input.seeds.frozen_op_ids,
    )
    edges = build_linear_edges_by_batch(nodes)
    scope = _graph_input_scope(schedule_input, nodes=nodes)
    try:
        analyzer = ScheduleGraphAnalysisService()
        summary = analyzer.analyze_precedence(nodes, edges, metrics_mode=metrics_mode)
        payload = graph_summary_to_dict(summary)
        projections = build_graph_dispatch_projections(
            schedule_input,
            mode=mode,
            score_requested=score_requested,
            score_weights=score_weights,
            nodes=nodes,
            edges=edges,
            payload=payload,
        )
    except NetworkXUnavailable as exc:
        public, diagnostics = _graph_error_projection(
            mode=mode,
            status="unavailable",
            reason="networkx_unavailable",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )
        return public, diagnostics, None, None
    except GraphBuildContractError as exc:
        public, diagnostics = _graph_error_projection(
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
        score_public=projections.score_public,
        score_diagnostics=projections.score_diagnostics,
        resource_matching_public=projections.resource_matching_public,
        resource_matching_diagnostics=projections.resource_matching_diagnostics,
    )
    return public, diagnostics, projections.ready_context, _graph_dispatch_mode_override(public)


def _cycle_error(diagnostics: Dict[str, Any]) -> ValidationError:
    """An available analysis always carries its cycle sample and count (_project_graph_analysis_payload)."""
    sample = list(diagnostics["cycle_edges_sample"])
    message = (f"工序图存在循环依赖，已按配置停止排产。请先检查这些环边样本：{sample}" if sample
               else "工序图存在循环依赖，已按配置停止排产。请先检查工艺路线里的前后工序关系。")
    return ValidationError(message, field=_GRAPH_CYCLE_DISABLED_REASON, details={
        "reason": _GRAPH_CYCLE_DISABLED_REASON,
        "cycle_edge_count": diagnostics["cycle_edge_count"],
        "cycle_edges_sample": sample,
    })


def _enforce_graph_dispatch_policy(
    *,
    mode: str,
    graph_block_on_cycle: str,
    public: Dict[str, Any],
    diagnostics: Optional[Dict[str, Any]],
) -> None:
    if mode != "on":
        return
    status = public["status"]
    if status != "available":
        reason = public["reason"]
        message = public["message"]
        raise ValidationError(
            f"工序图增强无法启用：{message}",
            field=reason,
            details={"reason": reason, "status": status},
        )
    if public["is_dag"]:
        return
    if graph_block_on_cycle == "yes":
        # Only unavailable/error projections come without diagnostics, and they were rejected above.
        raise _cycle_error(cast(Dict[str, Any], diagnostics))


def _graph_error_projection(
    *,
    mode: str,
    status: str,
    reason: str,
    exc: Exception,
    elapsed_ms: int,
    scope: Dict[str, Any],
) -> Tuple[Dict[str, Any], None]:
    public = {
        "mode": mode,
        "effective_mode": _effective_graph_analysis_mode(mode),
        "status": status,
        "reason": reason,
        "message": str(exc),
        "time_cost_ms": int(elapsed_ms),
        **scope,
    }
    return public, None


def _project_graph_analysis_payload(
    *,
    mode: str,
    graph_block_on_cycle: str = "no",
    payload: Dict[str, Any],
    elapsed_ms: int,
    scope: Dict[str, Any],
    score_public: Dict[str, Any],
    score_diagnostics: Dict[str, Any],
    resource_matching_public: Optional[Dict[str, Any]] = None,
    resource_matching_diagnostics: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cycle_edges = payload["cycle_edges"]
    topological_order = payload["topological_order"]
    critical_path = payload["critical_path"]
    warnings = payload["warnings"]
    node_metrics = payload["node_metrics"]

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
        **scope,
    }
    public.update(
        _graph_ready_public_fields(
            mode=mode,
            is_dag=bool(payload["is_dag"]),
            graph_block_on_cycle=graph_block_on_cycle,
        )
    )
    if score_public:
        public.update(score_public)
    if resource_matching_public:
        public["resource_matching"] = resource_matching_public
    diagnostics = {
        "topological_order_sample": sample_values(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "topological_order_count": int(len(topological_order)),
        "topological_order_truncated": is_truncated(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "critical_path_sample": sample_values(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "critical_path_count": int(len(critical_path)),
        "critical_path_truncated": is_truncated(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "cycle_edges_sample": sample_values(cycle_edges, _GRAPH_CYCLE_EDGE_SAMPLE_LIMIT),
        "cycle_edge_count": int(len(cycle_edges)),
        "warnings_sample": [_project_graph_warning(warning) for warning in warnings[:_GRAPH_WARNING_SAMPLE_LIMIT]],
        "warning_count": int(len(warnings)),
        "node_metrics_sample": _graph_node_metrics_sample(
            node_metrics=node_metrics,
            topological_order=topological_order,
            limit=_GRAPH_NODE_METRIC_SAMPLE_LIMIT,
        ),
        "node_metrics_count": int(len(node_metrics)),
        "node_metrics_truncated": len(node_metrics) > _GRAPH_NODE_METRIC_SAMPLE_LIMIT,
        "node_metrics_status": "available" if node_metrics else "skipped_basic_report",
    }
    if score_diagnostics:
        diagnostics.update(score_diagnostics)
    if resource_matching_diagnostics is not None:
        diagnostics["resource_matching"] = resource_matching_diagnostics
    return public, diagnostics


__all__ = [
    "ScheduleGraphDispatchPreparation",
    "prepare_schedule_graph_for_dispatch",
]
