from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from core.services.scheduler.graph.types import (
    GraphAnalysisSummary,
    GraphWarning,
    OperationGraphEdge,
    OperationGraphNode,
)


def test_operation_graph_node_defaults_are_json_serializable() -> None:
    node = OperationGraphNode(
        node_id="op:1",
        batch_id="B001",
        op_code="B001_10",
        seq=10,
        name="下料",
        duration_minutes=360,
    )

    assert is_dataclass(node)
    payload = asdict(node)
    assert payload["priority"] == "normal"
    assert payload["source"] == "internal"
    assert payload["status"] == "pending"
    assert payload["candidate_machine_ids"] == []
    assert payload["candidate_operator_ids"] == []
    assert payload["raw"] == {}
    json.dumps(payload, ensure_ascii=False)


def test_operation_graph_node_default_lists_are_isolated() -> None:
    first = OperationGraphNode(
        node_id="op:1",
        batch_id="B001",
        op_code="B001_10",
        seq=10,
        name="下料",
        duration_minutes=60,
    )
    second = OperationGraphNode(
        node_id="op:2",
        batch_id="B001",
        op_code="B001_20",
        seq=20,
        name="车削",
        duration_minutes=120,
    )

    first.candidate_machine_ids.append("CNC-01")
    assert second.candidate_machine_ids == []


def test_operation_graph_node_preserves_current_scheduler_fields() -> None:
    node = OperationGraphNode(
        node_id="op:2",
        batch_id="B001",
        op_code="B001_20",
        seq=20,
        name="外协热处理",
        duration_minutes=2880,
        part_no="P001",
        priority="urgent",
        source="external",
        status="pending",
        due_date="2026-05-20",
        op_type_id="OT-HT",
        supplier_id="SUP-01",
        ext_group_id="G-01",
        ext_merge_mode="merged",
        ext_group_total_days=2.0,
        merge_context_degraded=False,
        raw={"id": 2, "source": "external"},
    )

    payload = asdict(node)
    assert payload["source"] == "external"
    assert payload["ext_merge_mode"] == "merged"
    assert payload["ext_group_total_days"] == 2.0
    json.dumps(payload, ensure_ascii=False)


def test_operation_graph_edge_defaults_are_json_serializable() -> None:
    edge = OperationGraphEdge(from_node_id="op:1", to_node_id="op:2")

    payload = asdict(edge)
    assert payload == {
        "from_node_id": "op:1",
        "to_node_id": "op:2",
        "kind": "precedence",
        "lag_minutes": 0,
        "note": "",
    }
    json.dumps(payload, ensure_ascii=False)


def test_graph_warning_defaults_are_json_serializable() -> None:
    warning = GraphWarning(code="DUPLICATE_SEQ", message="同一批次存在重复工序顺序号")

    payload = asdict(warning)
    assert payload["data"] == {}
    json.dumps(payload, ensure_ascii=False)


def test_graph_analysis_summary_defaults_are_json_serializable() -> None:
    summary = GraphAnalysisSummary(node_count=2, edge_count=1, is_dag=True)

    payload = asdict(summary)
    assert payload["cycle_edges"] == []
    assert payload["topological_order"] == []
    assert payload["critical_path"] == []
    assert payload["critical_path_minutes"] == 0
    assert payload["warnings"] == []
    json.dumps(payload, ensure_ascii=False)


def test_graph_analysis_summary_can_embed_warnings() -> None:
    summary = GraphAnalysisSummary(
        node_count=1,
        edge_count=0,
        is_dag=True,
        warnings=[
            GraphWarning(
                code="ISOLATED_OPERATION",
                message="发现孤立工序",
                data={"node_id": "op:1"},
            )
        ],
    )

    payload = asdict(summary)
    assert payload["warnings"][0]["code"] == "ISOLATED_OPERATION"
    json.dumps(payload, ensure_ascii=False)
