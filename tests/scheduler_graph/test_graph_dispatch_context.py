from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.services.scheduler.graph.input_adapter import GraphInputContractError
from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode
from core.services.scheduler.run.schedule_graph_dispatch_context import build_predecessor_successor_maps


def _node(node_id: str, op_id: int) -> OperationGraphNode:
    return OperationGraphNode(
        node_id=node_id,
        batch_id="B1",
        op_code=f"OP-{op_id}",
        seq=op_id,
        name=f"op-{op_id}",
        duration_minutes=60,
        raw={"id": op_id},
    )


def test_build_predecessor_successor_maps_keeps_valid_edge_contract() -> None:
    predecessors, successors = build_predecessor_successor_maps(
        [_node("n1", 1), _node("n2", 2)],
        [OperationGraphEdge(from_node_id="n1", to_node_id="n2")],
    )

    assert predecessors == {1: set(), 2: {1}}
    assert successors == {1: {2}, 2: set()}


def test_build_predecessor_successor_maps_rejects_unknown_from_node() -> None:
    with pytest.raises(GraphInputContractError) as exc_info:
        build_predecessor_successor_maps(
            [_node("n1", 1)],
            [OperationGraphEdge(from_node_id="missing", to_node_id="n1")],
        )

    message = str(exc_info.value)
    assert "未知前置节点" in message
    assert "from_node_id" in message
    assert "missing" in message
    assert "edge_index=0" in message


def test_build_predecessor_successor_maps_rejects_unknown_to_node() -> None:
    with pytest.raises(GraphInputContractError) as exc_info:
        build_predecessor_successor_maps(
            [_node("n1", 1)],
            [OperationGraphEdge(from_node_id="n1", to_node_id="missing")],
        )

    message = str(exc_info.value)
    assert "未知后置节点" in message
    assert "to_node_id" in message
    assert "missing" in message
    assert "edge_index=0" in message


def test_build_predecessor_successor_maps_rejects_missing_endpoint_field() -> None:
    with pytest.raises(GraphInputContractError) as exc_info:
        build_predecessor_successor_maps(
            [_node("n1", 1)],
            [SimpleNamespace(from_node_id="n1")],
        )

    message = str(exc_info.value)
    assert "缺少字段 to_node_id" in message
    assert "edge_index=0" in message
