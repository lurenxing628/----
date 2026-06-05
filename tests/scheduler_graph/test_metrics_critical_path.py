"""回归测试：scheduler.graph.metrics.get_critical_path 对工序优先图求关键路径——线性链累加全部节点工时、分支取最长工时链、边的 lag_minutes 计入总时长、单节点退化；有环时透出 networkx.NetworkXUnfeasible，缺 duration_minutes/lag_minutes 时抛 KeyError 不静默当 0；build_duration_weighted_graph 不污染原图。"""

from __future__ import annotations

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


def test_linear_critical_path_includes_all_node_durations() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
            _node(node_id="op:C", op_code="B001_30", seq=30, duration_minutes=30),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:B", to_node_id="op:C"),
        ],
    )

    assert get_critical_path(graph) == (["op:A", "op:B", "op:C"], 60)


def test_branch_critical_path_chooses_longest_duration_chain() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path

    graph = _branch_graph()

    assert get_critical_path(graph) == (["op:A", "op:B", "op:D"], 120)


def test_edge_lag_minutes_are_included_in_critical_path_minutes() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B", lag_minutes=1440),
        ],
    )

    assert get_critical_path(graph) == (["op:A", "op:B"], 1470)


def test_single_node_graph_critical_path() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path, get_generation_index, get_impact_count

    graph = build_precedence_graph(
        [_node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10)],
        [],
    )

    assert get_critical_path(graph) == (["op:A"], 10)
    assert get_generation_index(graph) == {"op:A": 0}
    assert get_impact_count(graph, "op:A") == 0


def test_cycle_critical_path_exposes_networkx_unfeasible() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path
    from core.services.scheduler.graph.nx_runtime import import_networkx

    nx = import_networkx()
    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10),
            _node(node_id="op:B", op_code="B001_20", seq=20),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:B", to_node_id="op:A"),
        ],
    )

    with pytest.raises(nx.NetworkXUnfeasible):
        get_critical_path(graph)


def test_duration_weighted_graph_does_not_modify_original_graph() -> None:
    from core.services.scheduler.graph.metrics import build_duration_weighted_graph, get_critical_path

    graph = _branch_graph()
    before_nodes = _node_snapshot(graph)
    before_edges = _edge_snapshot(graph)

    weighted = build_duration_weighted_graph(graph)
    get_critical_path(graph)

    assert "__GRAPH_METRICS_SOURCE__" in weighted.nodes
    assert "__GRAPH_METRICS_SOURCE__" not in graph.nodes
    assert _node_snapshot(graph) == before_nodes
    assert _edge_snapshot(graph) == before_edges


def test_missing_duration_minutes_is_not_silently_treated_as_zero() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [_edge(from_node_id="op:A", to_node_id="op:B")],
    )
    del graph.nodes["op:A"]["duration_minutes"]

    with pytest.raises(KeyError):
        get_critical_path(graph)


def test_missing_lag_minutes_is_not_silently_treated_as_zero() -> None:
    from core.services.scheduler.graph.metrics import get_critical_path

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10, duration_minutes=10),
            _node(node_id="op:B", op_code="B001_20", seq=20, duration_minutes=20),
        ],
        [_edge(from_node_id="op:A", to_node_id="op:B")],
    )
    del graph.edges["op:A", "op:B"]["lag_minutes"]

    with pytest.raises(KeyError):
        get_critical_path(graph)


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


def _node_snapshot(graph: Any) -> List[Any]:
    return sorted((node_id, _plain_dict(data)) for node_id, data in graph.nodes(data=True))


def _edge_snapshot(graph: Any) -> List[Any]:
    return sorted((from_id, to_id, _plain_dict(data)) for from_id, to_id, data in graph.edges(data=True))


def _plain_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items()}
