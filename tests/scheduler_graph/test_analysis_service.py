from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from core.services.scheduler.graph import analysis_service
from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
from core.services.scheduler.graph.precedence_builder import GraphBuildContractError, build_precedence_graph
from core.services.scheduler.graph.types import GraphAnalysisSummary, OperationGraphEdge, OperationGraphNode

REPO_ROOT = Path(__file__).resolve().parents[2]


def _node(**overrides: Any) -> OperationGraphNode:
    data = {
        "node_id": "op:1",
        "batch_id": "B001",
        "op_code": "B001_10",
        "seq": 10,
        "name": "下料",
        "duration_minutes": 60,
    }
    data.update(overrides)
    return OperationGraphNode(**data)


def _edge(**overrides: Any) -> OperationGraphEdge:
    data = {
        "from_node_id": "op:1",
        "to_node_id": "op:2",
        "kind": "precedence",
        "lag_minutes": 0,
        "note": "测试边",
    }
    data.update(overrides)
    return OperationGraphEdge(**data)


def test_analyze_linear_batches_returns_summary_for_single_batch() -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10, duration_minutes=10),
        _node(node_id="op:2", op_code="B001_20", seq=20, duration_minutes=20),
        _node(node_id="op:3", op_code="B001_30", seq=30, duration_minutes=30),
    ]

    summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes)

    assert isinstance(summary, GraphAnalysisSummary)
    assert summary.node_count == 3
    assert summary.edge_count == 2
    assert summary.is_dag is True
    assert summary.cycle_edges == []
    assert summary.topological_order == ["op:1", "op:2", "op:3"]
    assert summary.critical_path == ["op:1", "op:2", "op:3"]
    assert summary.critical_path_minutes == 60
    assert set(summary.node_metrics) == {"op:1", "op:2", "op:3"}
    assert isinstance(summary.warnings, list)


def test_analyze_linear_batches_basic_mode_skips_node_metrics(monkeypatch: Any) -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10, duration_minutes=10),
        _node(node_id="op:2", op_code="B001_20", seq=20, duration_minutes=20),
    ]

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("basic metrics mode must not build node metrics")

    monkeypatch.setattr(analysis_service, "build_node_metrics", fail_if_called)

    summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes, metrics_mode="basic")

    assert summary.node_count == 2
    assert summary.edge_count == 1
    assert summary.topological_order == ["op:1", "op:2"]
    assert summary.critical_path == ["op:1", "op:2"]
    assert summary.critical_path_minutes == 30
    assert summary.node_metrics == {}


def test_analyze_linear_batches_reuses_precomputed_metrics_context(monkeypatch: Any) -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10, duration_minutes=10),
        _node(node_id="op:2", op_code="B001_20", seq=20, duration_minutes=20),
    ]
    captured: Dict[str, Any] = {}

    def fake_build_node_metrics(graph: Any, **kwargs: Any) -> Dict[str, Dict[str, Any]]:
        captured["node_count"] = graph.number_of_nodes()
        captured.update(kwargs)
        return {
            "op:1": {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 1,
                "generation_index": 0,
                "downstream_critical_minutes": 30,
            },
            "op:2": {
                "is_on_critical_path": True,
                "critical_path_rank": 1,
                "impact_count": 0,
                "generation_index": 1,
                "downstream_critical_minutes": 20,
            },
        }

    monkeypatch.setattr(analysis_service, "build_node_metrics", fake_build_node_metrics)

    summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes)

    assert summary.node_metrics["op:1"]["impact_count"] == 1
    assert captured["node_count"] == 2
    assert captured["topological_order"] == ["op:1", "op:2"]
    assert captured["critical_path"] == ["op:1", "op:2"]


def test_analyze_linear_batches_rejects_unknown_metrics_mode() -> None:
    with pytest.raises(ValueError, match="metrics_mode"):
        ScheduleGraphAnalysisService().analyze_linear_batches([], metrics_mode="debug")


def test_analyze_linear_batches_keeps_batches_separate() -> None:
    nodes = [
        _node(node_id="op:B001:10", batch_id="B001", op_code="B001_10", seq=10, duration_minutes=10),
        _node(node_id="op:B001:20", batch_id="B001", op_code="B001_20", seq=20, duration_minutes=20),
        _node(node_id="op:B002:10", batch_id="B002", op_code="B002_10", seq=10, duration_minutes=30),
        _node(node_id="op:B002:20", batch_id="B002", op_code="B002_20", seq=20, duration_minutes=40),
    ]

    summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes)

    assert summary.edge_count == 2
    assert summary.node_metrics["op:B001:10"]["impact_count"] == 1
    assert summary.node_metrics["op:B001:20"]["impact_count"] == 0
    assert summary.node_metrics["op:B002:10"]["impact_count"] == 1
    assert summary.node_metrics["op:B002:20"]["impact_count"] == 0


def test_cyclic_graph_returns_summary_without_calling_metrics(monkeypatch: Any) -> None:
    graph = build_precedence_graph(
        [
            _node(node_id="op:1", op_code="B001_10", seq=10),
            _node(node_id="op:2", op_code="B001_20", seq=20),
        ],
        [
            _edge(from_node_id="op:1", to_node_id="op:2"),
            _edge(from_node_id="op:2", to_node_id="op:1", kind="explicit"),
        ],
    )
    service = ScheduleGraphAnalysisService()

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("cyclic graph must not call metrics")

    monkeypatch.setattr(service, "_build_graph_for_linear_batches", lambda _nodes: graph)
    monkeypatch.setattr(analysis_service, "get_topological_generations", fail_if_called)
    monkeypatch.setattr(analysis_service, "get_critical_path", fail_if_called)
    monkeypatch.setattr(analysis_service, "build_node_metrics", fail_if_called)

    summary = service.analyze_linear_batches([])

    assert summary.is_dag is False
    assert summary.cycle_edges
    assert summary.topological_order == []
    assert summary.critical_path == []
    assert summary.critical_path_minutes == 0
    assert summary.node_metrics == {}
    assert "GRAPH_HAS_CYCLE" in [warning.code for warning in summary.warnings]


def test_bad_input_is_not_swallowed() -> None:
    with pytest.raises(GraphBuildContractError):
        ScheduleGraphAnalysisService().analyze_linear_batches([object()])  # type: ignore[list-item]


def test_analysis_service_import_does_not_import_networkx() -> None:
    code = r'''
import importlib
import json
import sys

sys.modules.pop("networkx", None)
importlib.import_module("core.services.scheduler.graph.analysis_service")
print(json.dumps({"networkx_loaded": "networkx" in sys.modules}, sort_keys=True))
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout.splitlines()[-1])
    assert payload == {"networkx_loaded": False}
