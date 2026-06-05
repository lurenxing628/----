"""单元测试：scheduler.graph.metrics 工序图影响度量——get_downstream/upstream_operations、get_impact_count（含菱形结构不重复计共享后继、多条独立链各算各的）、get_downstream_critical_minutes（含边 lag、缺 lag/duration 时保留 KeyError），以及 build_node_metrics 一次产出全节点 5 字段、只算一次关键路径不逐节点重建、可复用预计算上下文且不改动原图。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

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
    assert metrics["op:A"]["downstream_critical_minutes"] == 120
    assert metrics["op:D"]["downstream_critical_minutes"] == 10
    json.dumps(metrics, ensure_ascii=False)


def test_build_node_metrics_impact_count_diamond_does_not_double_count_shared_successor() -> None:
    from core.services.scheduler.graph.metrics import build_node_metrics, get_impact_count

    graph = _branch_graph()
    metrics = build_node_metrics(graph)

    assert metrics["op:A"]["impact_count"] == 3
    assert metrics["op:B"]["impact_count"] == 1
    assert metrics["op:C"]["impact_count"] == 1
    assert metrics["op:D"]["impact_count"] == 0
    assert {
        node_id: metrics[node_id]["impact_count"]
        for node_id in metrics
    } == {
        node_id: get_impact_count(graph, node_id)
        for node_id in metrics
    }


def test_build_node_metrics_impact_count_multi_independent_chains() -> None:
    from core.services.scheduler.graph.metrics import build_node_metrics

    graph = build_precedence_graph(
        [
            _node(node_id="op:A1", batch_id="B001", op_code="B001_10", seq=10),
            _node(node_id="op:A2", batch_id="B001", op_code="B001_20", seq=20),
            _node(node_id="op:A3", batch_id="B001", op_code="B001_30", seq=30),
            _node(node_id="op:B1", batch_id="B002", op_code="B002_10", seq=10),
            _node(node_id="op:B2", batch_id="B002", op_code="B002_20", seq=20),
        ],
        [
            _edge(from_node_id="op:A1", to_node_id="op:A2"),
            _edge(from_node_id="op:A2", to_node_id="op:A3"),
            _edge(from_node_id="op:B1", to_node_id="op:B2"),
        ],
    )

    metrics = build_node_metrics(graph)

    assert metrics["op:A1"]["impact_count"] == 2
    assert metrics["op:A2"]["impact_count"] == 1
    assert metrics["op:A3"]["impact_count"] == 0
    assert metrics["op:B1"]["impact_count"] == 1
    assert metrics["op:B2"]["impact_count"] == 0


def test_build_node_metrics_downstream_critical_minutes_includes_edge_lag() -> None:
    from core.services.scheduler.graph.metrics import build_node_metrics

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B", lag_minutes=5),
        ],
    )

    metrics = build_node_metrics(graph)

    assert metrics["op:A"]["downstream_critical_minutes"] == 35
    assert metrics["op:B"]["downstream_critical_minutes"] == 20


def test_downstream_critical_minutes_starts_from_requested_node() -> None:
    from core.services.scheduler.graph.metrics import get_downstream_critical_minutes

    graph = _branch_graph()

    assert get_downstream_critical_minutes(graph, "op:A") == 120
    assert get_downstream_critical_minutes(graph, "op:B") == 110
    assert get_downstream_critical_minutes(graph, "op:C") == 30
    assert get_downstream_critical_minutes(graph, "op:D") == 10


def test_downstream_critical_minutes_preserves_missing_lag_error() -> None:
    from core.services.scheduler.graph.metrics import get_downstream_critical_minutes

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
        ],
    )
    del graph.edges["op:A", "op:B"]["lag_minutes"]

    with pytest.raises(KeyError):
        get_downstream_critical_minutes(graph, "op:A")


def test_downstream_critical_minutes_preserves_missing_duration_error() -> None:
    from core.services.scheduler.graph.metrics import get_downstream_critical_minutes

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
        ],
    )
    del graph.nodes["op:B"]["duration_minutes"]

    with pytest.raises(KeyError):
        get_downstream_critical_minutes(graph, "op:A")


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


def test_build_node_metrics_does_not_call_single_node_impact_helper(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import metrics as graph_metrics

    graph = _linear_graph(8)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("build_node_metrics must batch impact_count calculation")

    monkeypatch.setattr(graph_metrics, "get_impact_count", fail_if_called)

    node_metrics = graph_metrics.build_node_metrics(graph)

    assert node_metrics["op:1"]["impact_count"] == 7
    assert node_metrics["op:8"]["impact_count"] == 0


def test_build_node_metrics_accepts_precomputed_context_equivalent_to_default() -> None:
    from core.services.scheduler.graph.metrics import (
        build_node_metrics,
        get_critical_path,
        get_generation_index,
        get_topological_order,
    )

    graph = _branch_graph()

    default_metrics = build_node_metrics(graph)
    topological_order = get_topological_order(graph)
    critical_path, _minutes = get_critical_path(graph)
    generation_index = get_generation_index(graph)
    precomputed_metrics = build_node_metrics(
        graph,
        topological_order=topological_order,
        critical_path=critical_path,
        generation_index=generation_index,
    )

    assert precomputed_metrics == default_metrics


def test_build_node_metrics_precomputed_context_skips_recomputing_context(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import metrics as graph_metrics

    graph = _branch_graph()
    topological_order = graph_metrics.get_topological_order(graph)
    critical_path, _minutes = graph_metrics.get_critical_path(graph)
    generation_index = graph_metrics.get_generation_index(graph)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("precomputed metrics context must not be recomputed")

    monkeypatch.setattr(graph_metrics, "get_topological_order", fail_if_called)
    monkeypatch.setattr(graph_metrics, "get_critical_path", fail_if_called)
    monkeypatch.setattr(graph_metrics, "get_generation_index", fail_if_called)

    metrics = graph_metrics.build_node_metrics(
        graph,
        topological_order=topological_order,
        critical_path=critical_path,
        generation_index=generation_index,
    )

    assert metrics["op:A"]["impact_count"] == 3
    assert metrics["op:A"]["downstream_critical_minutes"] == 120


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
