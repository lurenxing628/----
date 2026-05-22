from __future__ import annotations

from types import SimpleNamespace
from typing import List, Optional, Set

import pytest

from core.services.scheduler.graph.input_adapter import GraphInputContractError
from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode
from core.services.scheduler.run.schedule_graph_dispatch_context import (
    build_first_wave_ready_nodes,
    build_graph_resource_matching_projection,
    build_predecessor_successor_maps,
    graph_score_weights,
)


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


def _schedule_input(
    *,
    algo_op_ids: List[int],
    frozen_op_ids: Optional[Set[int]] = None,
    seed_op_ids: Optional[List[int]] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        algo_ops_to_schedule=[SimpleNamespace(id=op_id) for op_id in algo_op_ids],
        frozen_op_ids=set(frozen_op_ids or set()),
        seed_results=[{"op_id": op_id} for op_id in seed_op_ids or []],
    )


def test_build_predecessor_successor_maps_keeps_valid_edge_contract() -> None:
    predecessors, successors = build_predecessor_successor_maps(
        [_node("n1", 1), _node("n2", 2)],
        [OperationGraphEdge(from_node_id="n1", to_node_id="n2")],
    )

    assert predecessors == {1: set(), 2: {1}}
    assert successors == {1: {2}, 2: set()}


def test_build_first_wave_ready_nodes_report_uses_fixed_predecessors_and_node_order() -> None:
    nodes = [_node("n1", 1), _node("n2", 2), _node("n3", 3)]
    ready_nodes = build_first_wave_ready_nodes(
        _schedule_input(algo_op_ids=[2, 3], frozen_op_ids={1}),
        nodes=nodes,
        edges=[OperationGraphEdge(from_node_id="n1", to_node_id="n2")],
    )

    assert [node.raw["id"] for node in ready_nodes] == [2, 3]


def test_build_first_wave_ready_nodes_on_uses_graph_ready_context() -> None:
    nodes = [_node("n1", 1), _node("n2", 2), _node("n3", 3)]
    ready_nodes = build_first_wave_ready_nodes(
        _schedule_input(algo_op_ids=[2, 3]),
        nodes=nodes,
        edges=[],
        graph_ready_context={
            "schedulable_op_ids": {2, 3},
            "fixed_op_ids": {1},
            "predecessor_op_ids_by_op_id": {1: set(), 2: {1}, 3: set()},
        },
    )

    assert [node.raw["id"] for node in ready_nodes] == [2, 3]


def test_resource_matching_projection_skips_non_dag_without_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import resource_matching

    def _fail(_ready_nodes: object) -> object:
        raise AssertionError("non-DAG must not run resource matching")

    monkeypatch.setattr(resource_matching, "summarize_operation_machine_matching", _fail)

    public, diagnostics = build_graph_resource_matching_projection(
        mode="report",
        is_dag=False,
        graph_enhancement_allowed=False,
        graph_enhancement_disabled_reason=None,
        schedule_input=_schedule_input(algo_op_ids=[1]),
        nodes=[_node("n1", 1)],
        edges=[],
        graph_ready_context=None,
    )

    assert public["status"] == "skipped"
    assert public["reason"] == "graph_not_dag"
    assert public["matched_operation_count"] == 0
    assert diagnostics == {}


def test_resource_matching_projection_skips_on_without_graph_ready_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import resource_matching

    def _fail(_ready_nodes: object) -> object:
        raise AssertionError("disabled graph enhancement must not run resource matching")

    monkeypatch.setattr(resource_matching, "summarize_operation_machine_matching", _fail)

    public, diagnostics = build_graph_resource_matching_projection(
        mode="on",
        is_dag=True,
        graph_enhancement_allowed=False,
        graph_enhancement_disabled_reason="schedule_graph_cycle",
        schedule_input=_schedule_input(algo_op_ids=[1]),
        nodes=[_node("n1", 1)],
        edges=[],
        graph_ready_context=None,
    )

    assert public["status"] == "skipped"
    assert public["reason"] == "schedule_graph_cycle"
    assert diagnostics == {}


def test_resource_matching_contract_error_is_projected(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import resource_matching

    def _fail(_ready_nodes: object) -> object:
        raise resource_matching.GraphResourceMatchingContractError("bad matching input")

    monkeypatch.setattr(resource_matching, "summarize_operation_machine_matching", _fail)

    public, diagnostics = build_graph_resource_matching_projection(
        mode="report",
        is_dag=True,
        graph_enhancement_allowed=True,
        graph_enhancement_disabled_reason=None,
        schedule_input=_schedule_input(algo_op_ids=[1]),
        nodes=[_node("n1", 1)],
        edges=[],
        graph_ready_context=None,
    )

    assert public["status"] == "error"
    assert public["reason"] == "graph_resource_matching_contract_error"
    assert diagnostics == {}


def test_resource_matching_unknown_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import resource_matching

    def _fail(_ready_nodes: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(resource_matching, "summarize_operation_machine_matching", _fail)

    with pytest.raises(RuntimeError, match="boom"):
        build_graph_resource_matching_projection(
            mode="report",
            is_dag=True,
            graph_enhancement_allowed=True,
            graph_enhancement_disabled_reason=None,
            schedule_input=_schedule_input(algo_op_ids=[1]),
            nodes=[_node("n1", 1)],
            edges=[],
            graph_ready_context=None,
        )


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


def test_graph_score_weights_reads_downstream_weight_from_cfg() -> None:
    weights = graph_score_weights(
        SimpleNamespace(
            graph_critical_weight=500,
            graph_impact_weight=10,
            graph_downstream_weight=3,
        )
    )

    assert weights == {
        "critical_weight": 500,
        "impact_weight": 10,
        "downstream_minutes_weight": 3,
    }


@pytest.mark.parametrize("value", [True, -1])
def test_graph_score_weights_rejects_invalid_downstream_weight(value: object) -> None:
    cfg = SimpleNamespace(graph_critical_weight=500, graph_impact_weight=10, graph_downstream_weight=value)
    with pytest.raises(ValueError, match="graph_downstream_weight"):
        graph_score_weights(cfg)
