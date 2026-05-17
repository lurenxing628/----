from __future__ import annotations

import builtins
import importlib
import sys

import pytest

from core.services.scheduler.graph.precedence_builder import (
    GraphBuildContractError,
    build_linear_edges_by_batch,
    build_precedence_graph,
)
from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode


def _node(**overrides) -> OperationGraphNode:
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


def _edge(**overrides) -> OperationGraphEdge:
    data = {
        "from_node_id": "op:1",
        "to_node_id": "op:2",
        "kind": "precedence",
        "lag_minutes": 0,
        "note": "测试边",
    }
    data.update(overrides)
    return OperationGraphEdge(**data)


def test_build_linear_edges_for_single_batch() -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
        _node(node_id="op:3", op_code="B001_30", seq=30),
    ]

    edges = build_linear_edges_by_batch(nodes)
    graph = build_precedence_graph(nodes, edges)

    assert [(edge.from_node_id, edge.to_node_id) for edge in edges] == [("op:1", "op:2"), ("op:2", "op:3")]
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 2
    assert graph.has_edge("op:1", "op:2")
    assert graph.has_edge("op:2", "op:3")


def test_build_linear_edges_keeps_batches_separate() -> None:
    nodes = [
        _node(node_id="op:1", batch_id="B001", op_code="B001_10", seq=10),
        _node(node_id="op:2", batch_id="B001", op_code="B001_20", seq=20),
        _node(node_id="op:3", batch_id="B002", op_code="B002_10", seq=10),
        _node(node_id="op:4", batch_id="B002", op_code="B002_20", seq=20),
    ]

    edges = build_linear_edges_by_batch(nodes)
    graph = build_precedence_graph(nodes, edges)

    assert {(edge.from_node_id, edge.to_node_id) for edge in edges} == {("op:1", "op:2"), ("op:3", "op:4")}
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 2
    assert not graph.has_edge("op:2", "op:3")
    assert not graph.has_edge("op:4", "op:1")


def test_build_linear_edges_orders_by_seq_when_input_is_shuffled() -> None:
    nodes = [
        _node(node_id="op:3", op_code="B001_30", seq=30),
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
    ]

    edges = build_linear_edges_by_batch(nodes)

    assert [(edge.from_node_id, edge.to_node_id) for edge in edges] == [("op:1", "op:2"), ("op:2", "op:3")]


def test_duplicate_seq_keeps_stable_order_without_phase_6_validation() -> None:
    nodes = [
        _node(node_id="op:b", op_code="B001_B", seq=10),
        _node(node_id="op:a", op_code="B001_A", seq=10),
    ]

    edges = build_linear_edges_by_batch(nodes)

    assert [(edge.from_node_id, edge.to_node_id) for edge in edges] == [("op:a", "op:b")]
    assert edges[0].note == "batch=B001 seq 10 -> 10"


def test_external_previous_node_marks_edge_as_external_lag() -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10, source="internal"),
        _node(node_id="op:2", op_code="B001_20", seq=20, source="external"),
        _node(node_id="op:3", op_code="B001_30", seq=30, source="internal"),
    ]

    edges = build_linear_edges_by_batch(nodes)

    assert edges[0].kind == "precedence"
    assert edges[1].from_node_id == "op:2"
    assert edges[1].to_node_id == "op:3"
    assert edges[1].kind == "external_lag"
    assert edges[1].lag_minutes == 0


def test_build_precedence_graph_copies_node_attributes() -> None:
    node = _node(
        node_id="op:1",
        batch_id="B001",
        op_code="B001_10",
        seq=10,
        name="精加工",
        duration_minutes=90,
        part_no="P001",
        priority="urgent",
        source="external",
        status="frozen",
        due_date="2026-05-20",
        op_type_id="finish",
        machine_id="M01",
        operator_id="U01",
        supplier_id="S01",
        ext_group_id="EG01",
        ext_merge_mode="merged",
        ext_group_total_days=2.5,
        merge_context_degraded=True,
        candidate_machine_ids=("M01", "M02"),
        candidate_operator_ids=("U01", "U02"),
        raw={"row_id": 1, "source": "external"},
    )

    graph = build_precedence_graph([node], [])
    attrs = graph.nodes["op:1"]

    assert attrs == {
        "batch_id": "B001",
        "op_code": "B001_10",
        "seq": 10,
        "name": "精加工",
        "duration_minutes": 90,
        "part_no": "P001",
        "priority": "urgent",
        "source": "external",
        "status": "frozen",
        "due_date": "2026-05-20",
        "op_type_id": "finish",
        "machine_id": "M01",
        "operator_id": "U01",
        "supplier_id": "S01",
        "ext_group_id": "EG01",
        "ext_merge_mode": "merged",
        "ext_group_total_days": 2.5,
        "merge_context_degraded": True,
        "candidate_machine_ids": ["M01", "M02"],
        "candidate_operator_ids": ["U01", "U02"],
        "raw": {"row_id": 1, "source": "external"},
    }
    assert attrs["raw"] is not node.raw
    assert isinstance(attrs["raw"], dict)
    assert not any(value is node for value in attrs.values())


def test_build_precedence_graph_copies_edge_attributes() -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
    ]
    edge = _edge(kind="external_lag", lag_minutes=0, note="外协完成后进入下一道")

    graph = build_precedence_graph(nodes, [edge])

    assert graph.edges["op:1", "op:2"] == {
        "kind": "external_lag",
        "lag_minutes": 0,
        "note": "外协完成后进入下一道",
    }


def test_build_precedence_graph_rejects_duplicate_node_id_before_graph_build() -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:1", op_code="B001_20", seq=20),
    ]

    with pytest.raises(GraphBuildContractError, match="op:1"):
        build_precedence_graph(nodes, [])


@pytest.mark.parametrize(
    "edge",
    [
        _edge(from_node_id="op:404"),
        _edge(to_node_id="op:404"),
    ],
)
def test_build_precedence_graph_rejects_unknown_edge_endpoint(edge) -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
    ]

    with pytest.raises(GraphBuildContractError, match="op:404"):
        build_precedence_graph(nodes, [edge])


@pytest.mark.parametrize(
    "edge, message",
    [
        (_edge(kind="resource_conflict"), "kind"),
        (_edge(lag_minutes=-1), "lag_minutes"),
    ],
)
def test_build_precedence_graph_rejects_invalid_edge_contract(edge, message) -> None:
    nodes = [
        _node(node_id="op:1", op_code="B001_10", seq=10),
        _node(node_id="op:2", op_code="B001_20", seq=20),
    ]

    with pytest.raises(GraphBuildContractError, match=message):
        build_precedence_graph(nodes, [edge])


def test_precedence_builder_import_does_not_import_networkx(monkeypatch) -> None:
    sys.modules.pop("core.services.scheduler.graph.precedence_builder", None)
    sys.modules.pop("networkx", None)

    real_import = builtins.__import__
    imported = []

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "networkx" or name.startswith("networkx."):
            imported.append(name)
            raise AssertionError("precedence_builder import must not import networkx")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    importlib.import_module("core.services.scheduler.graph.precedence_builder")

    assert imported == []
