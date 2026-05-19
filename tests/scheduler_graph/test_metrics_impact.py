from __future__ import annotations

import json
from typing import Any, Dict, List

from core.services.scheduler.graph.precedence_builder import build_precedence_graph
from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode


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


def test_downstream_operations_and_impact_count() -> None:
    from core.services.scheduler.graph.metrics import get_downstream_operations, get_impact_count

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10),
            _node(node_id="op:B", op_code="B001_20", seq=20),
            _node(node_id="op:C", op_code="B001_30", seq=30),
            _node(node_id="op:D", op_code="B001_40", seq=40),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:B", to_node_id="op:C"),
            _edge(from_node_id="op:A", to_node_id="op:D"),
        ],
    )

    assert get_downstream_operations(graph, "op:A") == {"op:B", "op:C", "op:D"}
    assert get_downstream_operations(graph, "op:B") == {"op:C"}
    assert get_downstream_operations(graph, "op:C") == set()
    assert get_impact_count(graph, "op:A") == 3


def test_upstream_operations() -> None:
    from core.services.scheduler.graph.metrics import get_upstream_operations

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10),
            _node(node_id="op:B", op_code="B001_20", seq=20),
            _node(node_id="op:C", op_code="B001_30", seq=30),
            _node(node_id="op:D", op_code="B002_10", seq=10, batch_id="B002"),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:B", to_node_id="op:C"),
            _edge(from_node_id="op:D", to_node_id="op:C"),
        ],
    )

    assert get_upstream_operations(graph, "op:C") == {"op:A", "op:B", "op:D"}
    assert get_upstream_operations(graph, "op:A") == set()


def test_build_node_metrics_fields_and_json_values() -> None:
    from core.services.scheduler.graph.metrics import build_node_metrics

    graph = _branch_graph()

    metrics = build_node_metrics(graph)

    expected_fields = {
        "is_on_critical_path",
        "critical_path_rank",
        "impact_count",
        "generation_index",
        "downstream_critical_minutes",
    }
    assert set(metrics) == {"op:A", "op:B", "op:C", "op:D"}
    assert all(set(item) == expected_fields for item in metrics.values())
    assert metrics["op:B"]["is_on_critical_path"] is True
    assert metrics["op:B"]["critical_path_rank"] == 1
    assert metrics["op:C"]["is_on_critical_path"] is False
    assert metrics["op:C"]["critical_path_rank"] is None
    assert metrics["op:A"]["impact_count"] == 3
    assert metrics["op:D"]["downstream_critical_minutes"] == 10
    json.dumps(metrics, ensure_ascii=False)


def test_downstream_critical_minutes_starts_from_requested_node() -> None:
    from core.services.scheduler.graph.metrics import get_downstream_critical_minutes

    graph = _branch_graph()

    assert get_downstream_critical_minutes(graph, "op:A") == 120
    assert get_downstream_critical_minutes(graph, "op:B") == 110
    assert get_downstream_critical_minutes(graph, "op:C") == 30
    assert get_downstream_critical_minutes(graph, "op:D") == 10


def test_build_node_metrics_does_not_rebuild_longest_path_per_node(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import metrics as graph_metrics

    graph = _linear_graph(8)
    calls = {"get_critical_path": 0}
    original = graph_metrics.get_critical_path

    def _counted_get_critical_path(graph_arg: Any) -> Any:
        calls["get_critical_path"] += 1
        return original(graph_arg)

    monkeypatch.setattr(graph_metrics, "get_critical_path", _counted_get_critical_path)

    node_metrics = graph_metrics.build_node_metrics(graph)

    assert calls["get_critical_path"] == 1
    assert node_metrics["op:1"]["downstream_critical_minutes"] == 8
    assert node_metrics["op:8"]["downstream_critical_minutes"] == 1


def test_metrics_functions_do_not_modify_original_graph() -> None:
    from core.services.scheduler.graph.metrics import build_node_metrics, get_critical_path, get_topological_order

    graph = _branch_graph()
    before_nodes = _node_snapshot(graph)
    before_edges = _edge_snapshot(graph)

    get_topological_order(graph)
    get_critical_path(graph)
    build_node_metrics(graph)

    assert _node_snapshot(graph) == before_nodes
    assert _edge_snapshot(graph) == before_edges


def _branch_graph() -> Any:
    return build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=100),
            _node(node_id="op:C", op_code="B001_30", seq=30, duration_minutes=20),
            _node(node_id="op:D", op_code="B001_40", seq=40, duration_minutes=10),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:A", to_node_id="op:C"),
            _edge(from_node_id="op:B", to_node_id="op:D"),
            _edge(from_node_id="op:C", to_node_id="op:D"),
        ],
    )


def _linear_graph(node_count: int) -> Any:
    nodes = [
        _node(node_id=f"op:{index}", op_code=f"B001_{index * 10:03d}", seq=index * 10, duration_minutes=1)
        for index in range(1, node_count + 1)
    ]
    edges = [
        _edge(from_node_id=f"op:{index}", to_node_id=f"op:{index + 1}")
        for index in range(1, node_count)
    ]
    return build_precedence_graph(nodes, edges)


def _node_snapshot(graph: Any) -> List[Any]:
    return sorted((node_id, _plain_dict(data)) for node_id, data in graph.nodes(data=True))


def _edge_snapshot(graph: Any) -> List[Any]:
    return sorted((from_id, to_id, _plain_dict(data)) for from_id, to_id, data in graph.edges(data=True))


def _plain_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items()}
