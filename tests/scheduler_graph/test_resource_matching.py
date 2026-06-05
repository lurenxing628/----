"""回归测试：图调度 summarize_operation_machine_matching 用最大匹配做工序-设备匹配，每台设备只配一道工序，正确给出 matched/unmatched 工序与瓶颈设备；无 candidate_machine_ids 的 ready 工序记为 unmatched 并发 graph_resource_no_candidate_machine 警告而非回退全量设备；空 ready 集返回 empty 且不导入 NetworkX；重复 node_id 与非 OperationGraphNode 报 GraphResourceMatchingContractError；public 投影只含计数、样本留在 diagnostics，两者 JSON 安全且不暴露 Graph 对象；模块 import 不拉起 networkx。"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Tuple

import pytest

from core.services.scheduler.graph.resource_matching import (
    GraphResourceMatchingContractError,
    resource_matching_summary_to_diagnostics_dict,
    resource_matching_summary_to_public_dict,
    summarize_operation_machine_matching,
)
from core.services.scheduler.graph.types import OperationGraphNode


def _node(
    node_id: str,
    *,
    op_id: int,
    machines: Tuple[str, ...],
    seq: int = 10,
) -> OperationGraphNode:
    return OperationGraphNode(
        node_id=node_id,
        batch_id="B001",
        op_code=f"OP-{op_id}",
        seq=seq,
        name=f"op-{op_id}",
        duration_minutes=60,
        candidate_machine_ids=machines,
        raw={"id": op_id},
    )


def test_maximum_matching_keeps_each_machine_single_match() -> None:
    summary = summarize_operation_machine_matching(
        [
            _node("op:1", op_id=1, machines=("M1", "M2"), seq=10),
            _node("op:2", op_id=2, machines=("M2",), seq=20),
            _node("op:3", op_id=3, machines=("M2",), seq=30),
        ]
    )

    assert summary.status == "available"
    assert summary.reason == "ok"
    assert summary.ready_operation_count == 3
    assert summary.operation_with_candidate_count == 3
    assert summary.machine_count == 2
    assert summary.edge_count == 4
    assert summary.matched_operation_count == 2
    assert summary.unmatched_operation_ids in (("1",), ("2",), ("3",))
    assert summary.bottleneck_machine_ids == ("M2",)
    assert len(summary.matches) == 2
    assert len({match.operation_id for match in summary.matches}) == 2
    assert {match.operation_id for match in summary.matches}.issubset({"1", "2", "3"})
    assert {match.machine_id for match in summary.matches} <= {"M1", "M2"}


def test_matches_only_keep_operation_side_mapping() -> None:
    summary = summarize_operation_machine_matching([_node("op:1", op_id=1, machines=("M1",))])

    assert summary.matches == summary.matches[:1]
    assert len(summary.matches) == 1
    assert summary.matches[0].operation_node_id == "op:1"
    assert summary.matches[0].machine_node_id == "machine:M1"
    assert summary.matches[0].operation_id == "1"
    assert summary.matches[0].machine_id == "M1"


def test_missing_candidate_machine_becomes_unmatched_warning_without_fallback() -> None:
    summary = summarize_operation_machine_matching(
        [
            _node("op:1", op_id=1, machines=()),
            _node("op:2", op_id=2, machines=("M1",)),
        ]
    )

    assert summary.status == "available"
    assert summary.matched_operation_count == 1
    assert summary.operation_with_candidate_count == 1
    assert summary.unmatched_operation_ids == ("1",)
    assert summary.machine_count == 1
    assert summary.edge_count == 1
    assert summary.warnings == (
        {
            "code": "graph_resource_no_candidate_machine",
            "message": "ready 工序没有 candidate_machine_ids，资源匹配不会回退成全量设备。",
            "data": {"operation_id": "1", "operation_node_id": "op:1"},
        },
    )


def test_empty_ready_nodes_returns_empty_without_importing_networkx(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import resource_matching

    def _fail_import() -> object:
        raise AssertionError("empty ready set must not import NetworkX")

    monkeypatch.setattr(resource_matching, "import_networkx", _fail_import)

    summary = summarize_operation_machine_matching([])

    assert summary.status == "empty"
    assert summary.reason == "empty_ready_set"
    assert summary.ready_operation_count == 0
    assert summary.matched_operation_count == 0
    assert summary.unmatched_operation_ids == ()


def test_duplicate_node_id_rejected() -> None:
    with pytest.raises(GraphResourceMatchingContractError, match="重复 node_id"):
        summarize_operation_machine_matching(
            [
                _node("op:1", op_id=1, machines=("M1",)),
                _node("op:1", op_id=2, machines=("M2",)),
            ]
        )


def test_non_operation_graph_node_rejected() -> None:
    with pytest.raises(GraphResourceMatchingContractError, match="OperationGraphNode"):
        summarize_operation_machine_matching([{"node_id": "op:1"}])  # type: ignore[list-item]


def test_projection_dicts_are_json_safe_and_never_expose_graph_objects() -> None:
    summary = summarize_operation_machine_matching(
        [
            _node("op:1", op_id=1, machines=("M1", "M2"), seq=10),
            _node("op:2", op_id=2, machines=("M2",), seq=20),
            _node("op:3", op_id=3, machines=("M2",), seq=30),
        ]
    )

    public = resource_matching_summary_to_public_dict(summary)
    diagnostics = resource_matching_summary_to_diagnostics_dict(summary)

    json.dumps(public, ensure_ascii=False)
    json.dumps(diagnostics, ensure_ascii=False)
    assert "Graph" not in json.dumps({"public": public, "diagnostics": diagnostics}, ensure_ascii=False)
    assert public["unmatched_operation_count"] == 1
    assert public["bottleneck_machine_count"] == 1
    assert diagnostics["matches_count"] == 2
    assert diagnostics["unmatched_operation_ids_sample"] in (["2"], ["3"])
    assert diagnostics["bottleneck_machine_ids_sample"] == ["M2"]


def test_bottleneck_machine_ids_use_unmatched_candidates_and_edge_count_sorting() -> None:
    summary = summarize_operation_machine_matching(
        [
            _node("op:1", op_id=1, machines=("M1", "M2"), seq=10),
            _node("op:2", op_id=2, machines=("M1", "M2"), seq=20),
            _node("op:3", op_id=3, machines=("M2",), seq=30),
            _node("op:4", op_id=4, machines=("M3",), seq=40),
        ]
    )

    assert summary.ready_operation_count == 4
    assert summary.matched_operation_count == 3
    assert summary.unmatched_operation_ids in (("1",), ("2",), ("3",))
    assert summary.bottleneck_machine_ids[0] == "M2"
    assert set(summary.bottleneck_machine_ids).issubset({"M1", "M2"})


def test_public_has_counts_only_and_samples_stay_in_diagnostics() -> None:
    summary = summarize_operation_machine_matching(
        [
            _node("op:1", op_id=1, machines=("M1", "M2"), seq=10),
            _node("op:2", op_id=2, machines=("M2",), seq=20),
            _node("op:3", op_id=3, machines=("M2",), seq=30),
        ]
    )

    public = resource_matching_summary_to_public_dict(summary)
    diagnostics = resource_matching_summary_to_diagnostics_dict(summary)

    assert set(public) == {
        "status",
        "reason",
        "ready_operation_count",
        "operation_with_candidate_count",
        "machine_count",
        "edge_count",
        "matched_operation_count",
        "unmatched_operation_count",
        "bottleneck_machine_count",
    }
    forbidden_public_keys = {
        "unmatched_operation_sample",
        "unmatched_operation_ids_sample",
        "bottleneck_machine_sample",
        "bottleneck_machine_ids_sample",
        "matches_sample",
        "matches",
    }
    assert forbidden_public_keys.isdisjoint(public)
    assert diagnostics["matches_sample"]
    assert diagnostics["unmatched_operation_ids_sample"] in (["2"], ["3"])
    assert diagnostics["bottleneck_machine_ids_sample"] == ["M2"]


def test_resource_matching_module_import_does_not_import_networkx() -> None:
    sys.modules.pop("networkx", None)
    sys.modules.pop("core.services.scheduler.graph.resource_matching", None)

    importlib.import_module("core.services.scheduler.graph.resource_matching")

    assert "networkx" not in sys.modules
