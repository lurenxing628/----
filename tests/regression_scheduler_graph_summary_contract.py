from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional

from core.algorithms.evaluation import ScheduleMetrics
from core.services.scheduler.run.schedule_graph_report import _project_graph_analysis_payload
from core.services.scheduler.schedule_summary import build_result_summary
from core.services.scheduler.schedule_summary_types import SummaryBuildContext

_PUBLIC_FORBIDDEN_KEYS = {
    "topological_order_sample",
    "critical_path_sample",
    "node_metrics_sample",
    "graph_score_sample",
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


def _scope(size: int = 60) -> Dict[str, Any]:
    return {
        "input_scope": "all_algo_ops_with_frozen_markers",
        "total_algo_op_count": size,
        "reschedulable_unfrozen_op_count": size,
        "frozen_node_count": 0,
        "seed_result_count": 0,
    }


def _ctx(
    *,
    graph_analysis_public: Dict[str, Any],
    graph_analysis_diagnostics: Optional[Dict[str, Any]],
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
        scope=_scope(),
        score_public={
            "score_enabled": True,
            "score_metric_status": "available",
            "score_disabled_reason": None,
            "score_weight_summary": {
                "critical_weight": 500,
                "impact_weight": 10,
                "downstream_minutes_weight": 1,
            },
        },
        score_diagnostics={
            "graph_score_sample": [
                {
                    "op_id": 1,
                    "bonus": 1500,
                    "priority_key": [-1500.0, 0.0],
                    "is_on_critical_path": True,
                    "impact_count": 59,
                    "downstream_critical_minutes": 960,
                }
            ],
            "graph_score_sample_count": 60,
            "graph_score_sample_truncated": True,
        },
    )

    assert public["mode"] == "on"
    assert public["effective_mode"] == "graph_ready_queue"
    assert public["ready_queue_enabled"] is True
    assert public["score_enabled"] is True
    assert public["score_metric_status"] == "available"
    assert public["score_disabled_reason"] is None
    assert public["score_weight_summary"] == {
        "critical_weight": 500,
        "impact_weight": 10,
        "downstream_minutes_weight": 1,
    }
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
    assert diagnostics["node_metrics_status"] == "available"
    assert diagnostics["node_metrics_sample"][0]["node_id"] == "op:B001:OP000:0"
    assert diagnostics["graph_score_sample"][0]["op_id"] == 1
    assert diagnostics["graph_score_sample_count"] == 60
    assert diagnostics["graph_score_sample_truncated"] is True


def test_graph_warning_data_lists_are_sampled_inside_warning_projection() -> None:
    payload = _graph_payload(size=30)
    payload["warnings"] = [
        {
            "code": "GRAPH_HAS_CYCLE",
            "message": "cycle",
            "data": {
                "cycle_edges": [
                    {"from": f"op:{index}", "to": f"op:{index + 1}", "kind": "precedence"}
                    for index in range(30)
                ],
                "batch_id": "B001",
            },
        }
    ]

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(30),
    )

    warning = diagnostics["warnings_sample"][0]
    data = warning["data"]
    assert warning["warning_data_truncated"] is True
    assert len(data["cycle_edges_sample"]) == 20
    assert data["cycle_edges_count"] == 30
    assert data["cycle_edges_truncated"] is True
    assert data["batch_id"] == "B001"


def test_graph_warning_data_projection_is_deep_json_safe() -> None:
    payload = _graph_payload(size=3)
    payload["warnings"] = [
        {
            "code": "DUPLICATE_SEQ",
            "message": "duplicate",
            "data": {
                "node_ids": [object()] + [f"op:{index}" for index in range(30)],
                "nested": {
                    "bad": object(),
                    "items": [object(), {"ok": "yes"}],
                },
                "wide": {f"k{index}": index for index in range(25)},
            },
        }
    ]

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(3),
    )

    json.dumps(diagnostics, ensure_ascii=False)
    warning = diagnostics["warnings_sample"][0]
    data = warning["data"]
    assert warning["warning_data_truncated"] is True
    assert data["node_ids_sample"][0] == {"unsupported_value_type": "object"}
    assert data["node_ids_count"] == 31
    assert data["node_ids_truncated"] is True
    assert data["nested"]["bad"] == {"unsupported_value_type": "object"}
    assert data["nested"]["items"][0] == {"unsupported_value_type": "object"}
    assert data["wide"]["_field_count"] == 25
    assert data["wide"]["_fields_truncated"] is True


def test_graph_warning_data_projection_limits_top_level_fields() -> None:
    payload = _graph_payload(size=3)
    payload["warnings"] = [
        {
            "code": "WIDE_DATA",
            "message": "wide",
            "data": {f"k{index}": index for index in range(5000)},
        }
    ]

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(3),
    )

    data = diagnostics["warnings_sample"][0]["data"]
    assert diagnostics["warnings_sample"][0]["warning_data_truncated"] is True
    assert data["_field_count"] == 5000
    assert data["_fields_truncated"] is True
    assert "k20" not in data
    assert len(data) == 22
    json.dumps(diagnostics, ensure_ascii=False)


def test_graph_warning_projection_truncates_long_text_scalars() -> None:
    long_text = "很长的诊断文本" * 200
    payload = _graph_payload(size=3)
    payload["warnings"] = [
        {
            "code": "LONG_TEXT",
            "message": long_text,
            "data": {"note": long_text},
        }
    ]

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(3),
    )

    warning = diagnostics["warnings_sample"][0]
    assert warning["message_truncated"] is True
    assert warning["message_length"] == len(long_text)
    assert len(warning["message"]) == 500
    assert warning["warning_data_truncated"] is True
    assert warning["data"]["note"]["text_sample"] == long_text[:500]
    assert warning["data"]["note"]["text_length"] == len(long_text)
    assert warning["data"]["note"]["text_truncated"] is True
    json.dumps(diagnostics, ensure_ascii=False)


def test_graph_warning_data_projection_marks_non_dict_data() -> None:
    payload = _graph_payload(size=3)
    payload["warnings"] = [{"code": "BAD_DATA", "message": "bad", "data": [object()]}]

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(3),
    )

    warning = diagnostics["warnings_sample"][0]
    assert warning["warning_data_truncated"] is True
    assert warning["data"] == {"unsupported_data_type": "list"}
    json.dumps(diagnostics, ensure_ascii=False)


def test_graph_projection_marks_basic_report_when_node_metrics_are_skipped() -> None:
    payload = _graph_payload(size=3)
    payload["node_metrics"] = {}

    _public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=3,
        scope=_scope(3),
    )

    assert diagnostics["node_metrics_sample"] == []
    assert diagnostics["node_metrics_count"] == 0
    assert diagnostics["node_metrics_truncated"] is False
    assert diagnostics["node_metrics_status"] == "skipped_basic_report"


def test_summary_assembly_keeps_graph_public_and_diagnostics_separate() -> None:
    public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=_graph_payload(size=3),
        elapsed_ms=3,
        scope=_scope(3),
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


def test_known_graph_error_adds_top_level_warning_without_errors_or_diagnostics() -> None:
    public = {
        "mode": "report",
        "effective_mode": "report",
        "status": "unavailable",
        "reason": "networkx_unavailable",
        "message": "缺少可选依赖 networkx==3.1",
        "time_cost_ms": 3,
        "input_scope": "all_algo_ops_with_frozen_markers",
        "total_algo_op_count": 1,
        "reschedulable_unfrozen_op_count": 1,
        "frozen_node_count": 0,
        "seed_result_count": 0,
    }
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, result_status, result_summary_obj, _json, _time_cost_ms = build_result_summary(
        svc,
        ctx=_ctx(
            graph_analysis_public=public,
            graph_analysis_diagnostics=None,
        ),
    )

    assert result_status == "simulated"
    assert result_summary_obj["errors"] == []
    assert "graph_analysis" not in result_summary_obj.get("diagnostics", {})
    assert result_summary_obj["algo"]["graph_analysis"] == public
    assert result_summary_obj["warnings"] == ["工序图分析没有生成可用报告：缺少可选依赖 networkx==3.1"]
