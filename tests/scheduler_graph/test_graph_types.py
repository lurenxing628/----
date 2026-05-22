from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from core.services.scheduler.graph.types import (
    GraphAnalysisSummary,
    GraphWarning,
    OperationGraphEdge,
    OperationGraphNode,
)


def _make_node(**overrides) -> OperationGraphNode:
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


def test_operation_graph_node_candidate_ids_are_immutable() -> None:
    node = _make_node(candidate_machine_ids=["CNC-01"], candidate_operator_ids=["OP-01"])

    assert node.candidate_machine_ids == ("CNC-01",)
    assert node.candidate_operator_ids == ("OP-01",)

    with pytest.raises(AttributeError):
        node.candidate_machine_ids.append("CNC-02")
    with pytest.raises(FrozenInstanceError):
        node.candidate_machine_ids = ("CNC-02",)


def test_operation_graph_node_candidate_ids_strip_and_drop_blank_values() -> None:
    node = _make_node(candidate_machine_ids=[" CNC-01 ", "", "   "], candidate_operator_ids=[" OP-01 ", None])

    assert node.candidate_machine_ids == ("CNC-01",)
    assert node.candidate_operator_ids == ("OP-01",)


def test_operation_graph_node_raw_is_immutable_json_like_snapshot() -> None:
    node = _make_node(raw={"id": 1, "tags": ["a", "b"], "meta": {"x": 1}})

    with pytest.raises(TypeError):
        node.raw["id"] = 2

    with pytest.raises(TypeError):
        node.raw["meta"]["x"] = 2

    assert node.raw["tags"] == ("a", "b")
    json.dumps(asdict(node), ensure_ascii=False)


def test_operation_graph_node_raw_defensively_copies_source_mapping() -> None:
    raw = {"id": 1, "meta": {"x": 1}}
    node = _make_node(raw=raw)

    raw["id"] = 2
    raw["meta"]["x"] = 3

    assert node.raw["id"] == 1
    assert node.raw["meta"]["x"] == 1


@pytest.mark.parametrize(
    "field_name, kwargs",
    [
        ("node_id", {"node_id": ""}),
        ("batch_id", {"batch_id": ""}),
        ("op_code", {"op_code": ""}),
    ],
)
def test_operation_graph_node_rejects_blank_required_identifiers(field_name, kwargs) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_node(**kwargs)


def test_operation_graph_node_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="duration_minutes"):
        _make_node(duration_minutes=-1)


@pytest.mark.parametrize(
    "field_name, kwargs",
    [
        ("seq", {"seq": 1.5}),
        ("seq", {"seq": "10"}),
        ("seq", {"seq": True}),
        ("duration_minutes", {"duration_minutes": "60"}),
        ("duration_minutes", {"duration_minutes": True}),
    ],
)
def test_operation_graph_node_rejects_non_integer_runtime_fields(field_name, kwargs) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_node(**kwargs)


def test_graph_edge_and_summary_are_plain_python_value_objects() -> None:
    edge = OperationGraphEdge(from_node_id="op:1", to_node_id="op:2")
    warning = GraphWarning(code="DEMO", message="提示", data={"node_id": "op:1"})
    summary = GraphAnalysisSummary(
        node_count=2,
        edge_count=1,
        is_dag=True,
        cycle_edges=[],
        topological_order=["op:1", "op:2"],
        critical_path=["op:1", "op:2"],
        critical_path_minutes=60,
        node_metrics={
            "op:1": {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 1,
                "generation_index": 0,
                "downstream_critical_minutes": 60,
            }
        },
        warnings=[warning],
    )

    assert edge.kind == "precedence"
    assert summary.node_metrics["op:1"]["impact_count"] == 1
    assert summary.warnings[0].code == "DEMO"
    json.dumps(asdict(summary), ensure_ascii=False)


def test_graph_analysis_summary_defaults_are_json_serializable() -> None:
    summary = GraphAnalysisSummary(
        node_count=1,
        edge_count=0,
        is_dag=True,
        cycle_edges=[],
        topological_order=["op:1"],
        critical_path=["op:1"],
        critical_path_minutes=60,
    )

    assert summary.node_metrics == {}
    assert summary.warnings == []
    json.dumps(asdict(summary), ensure_ascii=False)
