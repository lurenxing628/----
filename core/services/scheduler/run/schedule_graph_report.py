from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch as _NATIVE_LINEAR_EDGES

from .schedule_graph_dispatch_context import (
    GRAPH_CYCLE_DISABLED_REASON as _GRAPH_CYCLE_DISABLED_REASON,
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
from .schedule_graph_projection_helpers import (
    _sample,
    _truncated,
)
from .schedule_graph_projection_helpers import (
    graph_node_metrics_sample as _graph_node_metrics_sample,
)
from .schedule_graph_projection_helpers import (
    project_graph_warning as _project_graph_warning,
)
from .schedule_graph_projections import build_graph_dispatch_projections
from .schedule_graph_score_projection import (
    graph_score_requested as _graph_score_requested,
)
from .schedule_graph_score_projection import (
    graph_score_weights as _graph_score_weights,
)
from .schedule_graph_score_projection import (
    score_disabled_public_fields as _score_disabled_public_fields,
)
from .schedule_input_contracts import ScheduleRunInput

_GRAPH_ANALYSIS_MODES = {"off", "report", "on"}
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


def prepare_schedule_graph_for_dispatch(
    schedule_input: ScheduleRunInput,
) -> ScheduleGraphDispatchPreparation:
    """为本次搜索构建一次图分析、派工和资源投影。"""
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
    score_weights = _graph_score_weights(schedule_input.cfg) if mode == "on" else None
    score_requested = bool(score_weights is not None and _graph_score_requested(score_weights))
    metrics_mode = "full" if score_requested else "basic"
    nodes = None
    try:
        nodes = build_operation_nodes_from_rows(
            schedule_input.algo_ops,
            batches=schedule_input.batches,
            resource_pool=schedule_input.resource_pool,
            frozen_op_ids=schedule_input.frozen_op_ids,
        )
        edges = build_linear_edges_by_batch(nodes)
        analyzer = ScheduleGraphAnalysisService()
        if build_linear_edges_by_batch is _NATIVE_LINEAR_EDGES:
            summary = analyzer.analyze_precedence(nodes, edges, metrics_mode=metrics_mode)
        else:
            # Unknown edge producers retain the legacy analysis/dispatch contract boundaries.
            summary = analyzer.analyze_precedence(nodes, _NATIVE_LINEAR_EDGES(nodes), metrics_mode=metrics_mode)
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
        scope = _graph_input_scope(schedule_input, nodes=nodes)
        public, diagnostics = _graph_unavailable_projection(mode=mode, exc=exc, elapsed_ms=_elapsed_ms(started), scope=scope)
        return public, diagnostics, None, None
    except GraphInputContractError as exc:
        scope = _graph_input_scope(schedule_input, nodes=nodes)
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
        scope = _graph_input_scope(schedule_input, nodes=nodes)
        public, diagnostics = _graph_contract_error_projection(
            mode=mode,
            status="build_error",
            reason="graph_build_contract_error",
            exc=exc,
            elapsed_ms=_elapsed_ms(started),
            scope=scope,
        )
        return public, diagnostics, None, None

    scope = _graph_input_scope(schedule_input, nodes=nodes)
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
    public = {
            "mode": mode,
            "effective_mode": _effective_graph_analysis_mode(mode),
            "status": "unavailable",
            "reason": "networkx_unavailable",
            "message": str(exc),
            "time_cost_ms": int(elapsed_ms),
            **dict(scope),
    }
    if mode == "on":
        public.update(
            _score_disabled_public_fields(
                reason="networkx_unavailable",
                score_weights=None,
                metric_status="unavailable",
            )
        )
    return public, None


def _graph_contract_error_projection(
    *,
    mode: str,
    status: str,
    reason: str,
    exc: Exception,
    elapsed_ms: int,
    scope: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    public = {
            "mode": mode,
            "effective_mode": _effective_graph_analysis_mode(mode),
            "status": status,
            "reason": reason,
            "message": str(exc),
            "time_cost_ms": int(elapsed_ms),
            **dict(scope),
    }
    if mode == "on":
        public.update(
            _score_disabled_public_fields(
                reason=reason,
                score_weights=None,
                metric_status="unavailable",
            )
        )
    return public, None


def _project_graph_analysis_payload(
    *,
    mode: str,
    graph_block_on_cycle: str = "no",
    payload: Dict[str, Any],
    elapsed_ms: int,
    scope: Dict[str, Any],
    score_public: Optional[Dict[str, Any]] = None,
    score_diagnostics: Optional[Dict[str, Any]] = None,
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
        **dict(scope),
    }
    public.update(
        _graph_ready_public_fields(
            mode=mode,
            is_dag=bool(payload["is_dag"]),
            graph_block_on_cycle=graph_block_on_cycle,
        )
    )
    if score_public:
        public.update(dict(score_public))
    if resource_matching_public:
        public["resource_matching"] = dict(resource_matching_public)
    diagnostics = {
        "topological_order_sample": _sample(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "topological_order_count": int(len(topological_order)),
        "topological_order_truncated": _truncated(topological_order, _GRAPH_TOPOLOGICAL_SAMPLE_LIMIT),
        "critical_path_sample": _sample(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "critical_path_count": int(len(critical_path)),
        "critical_path_truncated": _truncated(critical_path, _GRAPH_CRITICAL_PATH_SAMPLE_LIMIT),
        "cycle_edges_sample": _sample(cycle_edges, _GRAPH_CYCLE_EDGE_SAMPLE_LIMIT),
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
        diagnostics.update(dict(score_diagnostics))
    if resource_matching_diagnostics is not None:
        diagnostics["resource_matching"] = dict(resource_matching_diagnostics)
    return public, diagnostics


__all__ = [
    "ScheduleGraphDispatchPreparation",
    "prepare_schedule_graph_for_dispatch",
]
