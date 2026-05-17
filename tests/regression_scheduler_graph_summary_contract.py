from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict

from core.algorithms.evaluation import ScheduleMetrics
from core.services.scheduler.run.schedule_graph_report import _project_graph_analysis_payload
from core.services.scheduler.schedule_summary import build_result_summary
from core.services.scheduler.schedule_summary_types import SummaryBuildContext

_PUBLIC_FORBIDDEN_KEYS = {
    "topological_order_sample",
    "critical_path_sample",
    "node_metrics_sample",
    "nodes",
    "edges",
    "raw",
}
_DIAGNOSTIC_FORBIDDEN_KEYS = {
    "topological_order",
    "critical_path",
    "node_metrics",
    "nodes",
    "edges",
    "raw",
}


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=1.0,
        enforce_ready_default="yes",
        prefer_primary_skill="yes",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        auto_assign_persist="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="improve",
        time_budget_seconds=5,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
        graph_analysis_mode="report",
        graph_block_on_cycle="no",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_debug_export="no",
    )


def _graph_payload(size: int = 60) -> Dict[str, Any]:
    node_ids = [f"op:B001:OP{i:03d}:{i}" for i in range(size)]
    return {
        "node_count": size,
        "edge_count": size - 1,
        "is_dag": True,
        "cycle_edges": [
            {"from": node_ids[i], "to": node_ids[(i + 1) % size], "kind": "precedence"}
            for i in range(min(25, size))
        ],
        "topological_order": list(node_ids[:25]),
        "critical_path": list(node_ids[:55]),
        "critical_path_minutes": 960,
        "node_metrics": {
            node_id: {
                "is_on_critical_path": index < 55,
                "critical_path_rank": index if index < 55 else None,
                "impact_count": max(size - index - 1, 0),
                "generation_index": index,
                "downstream_critical_minutes": max(960 - index, 0),
            }
            for index, node_id in enumerate(node_ids)
        },
        "warnings": [
            {"code": "W", "message": f"warning {index}", "data": {"index": index}}
            for index in range(25)
        ],
    }


def _ctx(
    *,
    graph_analysis_public: Dict[str, Any],
    graph_analysis_diagnostics: Dict[str, Any],
) -> SummaryBuildContext:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    result = SimpleNamespace(
        op_id=1,
        batch_id="B001",
        machine_id="MC1",
        operator_id="OP1",
        start_time=start,
        end_time=end,
        source="internal",
    )
    summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=2.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    return SummaryBuildContext(
        cfg=_cfg(),
        version=3,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={"B001": SimpleNamespace(batch_id="B001", due_date="2026-04-02", status="pending")},
        operations=[],
        results=[result],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[
            {
                "source": "candidate_rejected",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "origin": {"type": "ValidationError", "field": "resource"},
            }
        ],
        improvement_trace=[],
        frozen_op_ids=set(),
        readiness_gate_enabled=True,
        graph_analysis_public=graph_analysis_public,
        graph_analysis_diagnostics=graph_analysis_diagnostics,
        simulate=True,
        t0=0.0,
    )


def test_graph_projection_keeps_public_summary_small_and_samples_diagnostics() -> None:
    public, diagnostics = _project_graph_analysis_payload(
        mode="on",
        payload=_graph_payload(),
        elapsed_ms=7,
    )

    assert public["mode"] == "on"
    assert public["effective_mode"] == "report_only"
    assert public["status"] == "available"
    assert public["node_count"] == 60
    assert public["edge_count"] == 59
    assert public["critical_path_node_count"] == 55
    assert public["warning_count"] == 25
    assert public["cycle_edge_count"] == 25
    assert public["time_cost_ms"] == 7
    assert _PUBLIC_FORBIDDEN_KEYS.isdisjoint(public)

    assert _DIAGNOSTIC_FORBIDDEN_KEYS.isdisjoint(diagnostics)
    assert len(diagnostics["topological_order_sample"]) == 20
    assert diagnostics["topological_order_count"] == 25
    assert diagnostics["topological_order_truncated"] is True
    assert len(diagnostics["critical_path_sample"]) == 50
    assert diagnostics["critical_path_count"] == 55
    assert diagnostics["critical_path_truncated"] is True
    assert len(diagnostics["cycle_edges_sample"]) == 20
    assert diagnostics["cycle_edge_count"] == 25
    assert len(diagnostics["warnings_sample"]) == 20
    assert diagnostics["warning_count"] == 25
    assert len(diagnostics["node_metrics_sample"]) == 20
    assert diagnostics["node_metrics_count"] == 60
    assert diagnostics["node_metrics_truncated"] is True
    assert diagnostics["node_metrics_sample"][0]["node_id"] == "op:B001:OP000:0"


def test_summary_assembly_keeps_graph_public_and_diagnostics_separate() -> None:
    public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=_graph_payload(size=3),
        elapsed_ms=3,
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _json, _time_cost_ms = build_result_summary(
        svc,
        ctx=_ctx(
            graph_analysis_public=public,
            graph_analysis_diagnostics=diagnostics,
        ),
    )

    graph_public = result_summary_obj["algo"]["graph_analysis"]
    graph_diagnostics = result_summary_obj["diagnostics"]["graph_analysis"]
    assert graph_public == public
    assert graph_diagnostics == diagnostics
    assert "optimizer" in result_summary_obj["diagnostics"]
    assert "graph_analysis" not in result_summary_obj["diagnostics"]["optimizer"]
    assert _PUBLIC_FORBIDDEN_KEYS.isdisjoint(graph_public)
