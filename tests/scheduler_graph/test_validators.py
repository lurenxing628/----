from __future__ import annotations

import builtins
import importlib
import json
import sys
from dataclasses import asdict
from typing import Any, Dict, List

from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch, build_precedence_graph
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


def _linear_graph() -> Any:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
        _node(node_id="op:3", op_code="B001_30", seq=30),
    ]
    edges = [
        _edge(from_node_id="op:1", to_node_id="op:2"),
        _edge(from_node_id="op:2", to_node_id="op:3"),
    ]
    return build_precedence_graph(nodes, edges)


def _cycle_graph() -> Any:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
        _node(node_id="op:3", op_code="B001_30", seq=30),
    ]
    edges = [
        _edge(from_node_id="op:1", to_node_id="op:2", kind="precedence"),
        _edge(from_node_id="op:2", to_node_id="op:3", kind="external_lag"),
        _edge(from_node_id="op:3", to_node_id="op:1", kind="explicit"),
    ]
    return build_precedence_graph(nodes, edges)


def _warning_codes(warnings: List[Any]) -> List[str]:
    return [warning.code for warning in warnings]


def test_validators_import_does_not_import_networkx(monkeypatch: Any) -> None:
    sys.modules.pop("core.services.scheduler.graph.validators", None)
    sys.modules.pop("networkx", None)

    real_import = builtins.__import__
    imported: List[str] = []

    def tracking_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "networkx" or name.startswith("networkx."):
            imported.append(name)
            raise AssertionError("validators import must not import networkx")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    module = importlib.import_module("core.services.scheduler.graph.validators")

    assert imported == []
    assert hasattr(module, "is_dag")


def test_dag_graph_reports_true_and_no_cycle_edges() -> None:
    from core.services.scheduler.graph.validators import find_cycle_edges, is_dag

    graph = _linear_graph()

    assert is_dag(graph) is True
    assert find_cycle_edges(graph) == []


def test_cyclic_graph_reports_false_and_cycle_edge_details() -> None:
    from core.services.scheduler.graph.validators import find_cycle_edges, is_dag

    graph = _cycle_graph()

    assert is_dag(graph) is False
    cycle_edges = find_cycle_edges(graph)

    assert cycle_edges
    assert {frozenset(item.keys()) for item in cycle_edges} == {
        frozenset({"from", "to", "from_op_code", "to_op_code", "kind"})
    }
    assert {item["kind"] for item in cycle_edges} == {"precedence", "external_lag", "explicit"}


def test_isolated_operation_returns_warning() -> None:
    from core.services.scheduler.graph.validators import collect_graph_warnings, find_isolated_nodes

    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
        _node(node_id="op:3", op_code="B001_30", seq=30),
    ]
    graph = build_precedence_graph(nodes, [_edge(from_node_id="op:2", to_node_id="op:3")])

    warnings = collect_graph_warnings(graph)
    isolated_warning = next(warning for warning in warnings if warning.code == "ISOLATED_OPERATION")

    assert find_isolated_nodes(graph) == ["op:1"]
    assert isolated_warning.message == "发现孤立工序：B001_10"
    assert isolated_warning.data == {
        "node_id": "op:1",
        "op_code": "B001_10",
        "batch_id": "B001",
        "seq": 10,
    }


def test_duplicate_seq_in_same_batch_returns_warning_with_stable_order() -> None:
    from core.services.scheduler.graph.validators import find_duplicate_seq_warnings

    nodes = [
        _node(node_id="op:b", batch_id="B001", op_code="B001_B", seq=10),
        _node(node_id="op:a", batch_id="B001", op_code="B001_A", seq=10),
        _node(node_id="op:c", batch_id="B001", op_code="B001_C", seq=20),
    ]
    graph = build_precedence_graph(nodes, [])

    warnings = find_duplicate_seq_warnings(graph)

    assert len(warnings) == 1
    assert warnings[0].code == "DUPLICATE_SEQ"
    assert warnings[0].data == {
        "batch_id": "B001",
        "seq": 10,
        "node_ids": ["op:a", "op:b"],
        "op_codes": ["B001_A", "B001_B"],
    }


def test_same_seq_in_different_batches_does_not_return_duplicate_seq_warning() -> None:
    from core.services.scheduler.graph.validators import collect_graph_warnings

    nodes = [
        _node(node_id="op:1", batch_id="B001", op_code="B001_10", seq=10),
        _node(node_id="op:2", batch_id="B002", op_code="B002_10", seq=10),
    ]
    graph = build_precedence_graph(nodes, [])

    warnings = collect_graph_warnings(graph)

    assert "DUPLICATE_SEQ" not in _warning_codes(warnings)


def test_warnings_are_json_serializable() -> None:
    from core.services.scheduler.graph.validators import collect_graph_warnings

    nodes = [
        _node(node_id="op:1", batch_id="B001", op_code="B001_10", seq=10),
        _node(node_id="op:2", batch_id="B001", op_code="B001_20", seq=10),
        _node(node_id="op:3", batch_id="B002", op_code="B002_10", seq=10),
    ]
    graph = build_precedence_graph(nodes, [])
    warnings = collect_graph_warnings(graph)

    payload = [asdict(warning) for warning in warnings]

    json.dumps(payload, ensure_ascii=False)
    assert all(isinstance(warning["data"], dict) for warning in payload)
    assert any(warning["code"] == "DUPLICATE_SEQ" for warning in payload)
    assert any(warning["code"] == "ISOLATED_OPERATION" for warning in payload)


def test_validators_do_not_modify_original_graph() -> None:
    from core.services.scheduler.graph.validators import collect_graph_warnings, find_cycle_edges, is_dag

    graph = _cycle_graph()
    before_nodes = _node_snapshot(graph)
    before_edges = _edge_snapshot(graph)

    is_dag(graph)
    find_cycle_edges(graph)
    collect_graph_warnings(graph)

    assert _node_snapshot(graph) == before_nodes
    assert _edge_snapshot(graph) == before_edges


def test_cycle_detection_does_not_import_phase_8_metrics(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import validators

    sys.modules.pop("core.services.scheduler.graph.metrics", None)
    graph = _cycle_graph()

    class _FakeNx:
        class NetworkXNoCycle(Exception):
            pass

        def is_directed_acyclic_graph(self, graph: Any) -> bool:
            return False

        def find_cycle(self, graph: Any, orientation: str = "original") -> List[Any]:
            return [("op:1", "op:2", "forward"), ("op:2", "op:3", "forward"), ("op:3", "op:1", "forward")]

        def __getattr__(self, name: str) -> Any:
            if name in ("topological_sort", "dag_longest_path", "topological_generations"):
                raise AssertionError(f"{name} belongs to phase 8")
            raise AttributeError(name)

    monkeypatch.setattr(validators, "import_networkx", lambda: _FakeNx())

    assert validators.is_dag(graph) is False
    assert validators.find_cycle_edges(graph)
    assert "core.services.scheduler.graph.metrics" not in sys.modules


def test_validators_chain_with_phase_6_precedence_builder() -> None:
    from core.services.scheduler.graph.validators import find_duplicate_seq_warnings, is_dag

    linear_nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
        _node(node_id="op:3", op_code="B001_30", seq=30),
    ]
    linear_edges = build_linear_edges_by_batch(linear_nodes)
    linear_graph = build_precedence_graph(linear_nodes, linear_edges)

    duplicate_nodes = [
        _node(node_id="op:b", op_code="B001_B", seq=10),
        _node(node_id="op:a", op_code="B001_A", seq=10),
    ]
    duplicate_edges = build_linear_edges_by_batch(duplicate_nodes)
    duplicate_graph = build_precedence_graph(duplicate_nodes, duplicate_edges)

    assert is_dag(linear_graph) is True
    assert find_duplicate_seq_warnings(duplicate_graph)[0].code == "DUPLICATE_SEQ"


def _node_snapshot(graph: Any) -> List[Any]:
    return sorted((node_id, _plain_dict(data)) for node_id, data in graph.nodes(data=True))


def _edge_snapshot(graph: Any) -> List[Any]:
    return sorted((from_id, to_id, _plain_dict(data)) for from_id, to_id, data in graph.edges(data=True))


def _plain_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items()}
