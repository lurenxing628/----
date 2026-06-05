"""测试：scheduler_graph.exporter 把图与摘要导出为可 JSON 序列化的 plain dict——graph_to_plain_dict 按节点/边稳定排序、只导出承诺字段（不含 raw/due_date）、不修改原图；graph_summary_to_dict 可序列化且返回与原 summary 深拷贝隔离的 payload（改 payload 不影响 summary 的 node_metrics/cycle_edges/topological_order/critical_path）。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from core.services.scheduler.graph.exporter import graph_summary_to_dict, graph_to_plain_dict, graph_warning_to_dict
from core.services.scheduler.graph.precedence_builder import build_precedence_graph
from core.services.scheduler.graph.types import (
    GraphAnalysisSummary,
    GraphWarning,
    OperationGraphEdge,
    OperationGraphNode,
)


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


def test_graph_to_plain_dict_is_json_serializable_with_stable_order() -> None:
    graph = build_precedence_graph(
        [
            _node(node_id="op:B002:20", batch_id="B002", op_code="B002_20", seq=20, duration_minutes=40),
            _node(node_id="op:B001:20", batch_id="B001", op_code="B001_20", seq=20, duration_minutes=30),
            _node(node_id="op:B002:10", batch_id="B002", op_code="B002_10", seq=10, duration_minutes=10),
            _node(node_id="op:B001:10", batch_id="B001", op_code="B001_10", seq=10, duration_minutes=20),
        ],
        [
            _edge(from_node_id="op:B002:10", to_node_id="op:B002:20"),
            _edge(from_node_id="op:B001:10", to_node_id="op:B001:20"),
        ],
    )

    payload = graph_to_plain_dict(graph)

    json.dumps(payload, ensure_ascii=False)
    assert [item["id"] for item in payload["nodes"]] == [
        "op:B001:10",
        "op:B001:20",
        "op:B002:10",
        "op:B002:20",
    ]
    assert payload["edges"] == [
        {
            "from": "op:B001:10",
            "to": "op:B001:20",
            "kind": "precedence",
            "lag_minutes": 0,
        },
        {
            "from": "op:B002:10",
            "to": "op:B002:20",
            "kind": "precedence",
            "lag_minutes": 0,
        },
    ]


def test_graph_summary_to_dict_is_json_serializable() -> None:
    warning = GraphWarning(
        code="DUPLICATE_SEQ",
        message="同一批次存在重复工序顺序号：batch_id=B001, seq=10",
        data={"batch_id": "B001", "seq": 10, "node_ids": ["op:1"]},
    )
    summary = GraphAnalysisSummary(
        node_count=2,
        edge_count=1,
        is_dag=True,
        cycle_edges=[],
        topological_order=["op:1", "op:2"],
        critical_path=["op:1", "op:2"],
        critical_path_minutes=90,
        node_metrics={
            "op:1": {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 1,
                "generation_index": 0,
                "downstream_critical_minutes": 90,
            }
        },
        warnings=[warning],
    )

    payload = graph_summary_to_dict(summary)

    json.dumps(payload, ensure_ascii=False)
    assert payload["node_metrics"] == summary.node_metrics
    assert payload["warnings"] == [graph_warning_to_dict(warning)]


def test_graph_summary_to_dict_returns_mutation_isolated_payload() -> None:
    summary = GraphAnalysisSummary(
        node_count=1,
        edge_count=0,
        is_dag=True,
        cycle_edges=[{"from": "op:1", "to": "op:2", "kind": "precedence"}],
        topological_order=["op:1"],
        critical_path=["op:1"],
        critical_path_minutes=60,
        node_metrics={
            "op:1": {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 0,
                "generation_index": 0,
                "downstream_critical_minutes": 60,
            }
        },
        warnings=[],
    )

    payload = graph_summary_to_dict(summary)

    assert payload["node_metrics"] is not summary.node_metrics
    assert payload["node_metrics"]["op:1"] is not summary.node_metrics["op:1"]
    assert payload["cycle_edges"] is not summary.cycle_edges
    assert payload["cycle_edges"][0] is not summary.cycle_edges[0]
    assert payload["topological_order"] is not summary.topological_order
    assert payload["critical_path"] is not summary.critical_path

    payload["node_metrics"]["op:1"]["impact_count"] = 999
    payload["cycle_edges"][0]["kind"] = "changed"
    payload["topological_order"].append("op:2")
    payload["critical_path"].append("op:2")

    assert summary.node_metrics["op:1"]["impact_count"] == 0
    assert summary.cycle_edges[0]["kind"] == "precedence"
    assert summary.topological_order == ["op:1"]
    assert summary.critical_path == ["op:1"]


def test_graph_to_plain_dict_does_not_modify_graph() -> None:
    graph = build_precedence_graph(
        [
            _node(node_id="op:1", op_code="B001_10", seq=10),
            _node(node_id="op:2", op_code="B001_20", seq=20),
        ],
        [_edge(from_node_id="op:1", to_node_id="op:2")],
    )
    before_nodes = _node_snapshot(graph)
    before_edges = _edge_snapshot(graph)

    graph_to_plain_dict(graph)

    assert _node_snapshot(graph) == before_nodes
    assert _edge_snapshot(graph) == before_edges


def test_graph_to_plain_dict_exports_only_promised_fields() -> None:
    graph = build_precedence_graph(
        [
            _node(
                node_id="op:1",
                op_code="B001_10",
                seq=10,
                name="精加工",
                raw={"row_id": 1},
                due_date="2026-05-20",
            )
        ],
        [],
    )

    payload = graph_to_plain_dict(graph)

    assert set(payload["nodes"][0]) == {"id", "batch_id", "op_code", "seq", "duration_minutes"}
    assert "raw" not in payload["nodes"][0]
    assert "due_date" not in payload["nodes"][0]


def _node_snapshot(graph: Any) -> List[Any]:
    return sorted((node_id, _plain_dict(data)) for node_id, data in graph.nodes(data=True))


def _edge_snapshot(graph: Any) -> List[Any]:
    return sorted((from_id, to_id, _plain_dict(data)) for from_id, to_id, data in graph.edges(data=True))


def _plain_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items()}
