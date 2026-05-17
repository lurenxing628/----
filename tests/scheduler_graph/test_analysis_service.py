from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    monkeypatch.setattr(analysis_service, "get_topological_order", fail_if_called)
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
