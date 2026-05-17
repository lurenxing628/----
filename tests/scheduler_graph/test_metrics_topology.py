from __future__ import annotations

import builtins
import importlib
import sys
from typing import Any, List

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


def test_metrics_import_does_not_import_networkx(monkeypatch: Any) -> None:
    sys.modules.pop("core.services.scheduler.graph.metrics", None)
    sys.modules.pop("networkx", None)

    real_import = builtins.__import__
    imported: List[str] = []

    def tracking_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "networkx" or name.startswith("networkx."):
            imported.append(name)
            raise AssertionError("metrics import must not import networkx")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    module = importlib.import_module("core.services.scheduler.graph.metrics")

    assert imported == []
    assert hasattr(module, "get_topological_order")


def test_linear_topological_order_and_generation_index() -> None:
    from core.services.scheduler.graph.metrics import get_generation_index, get_topological_order

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10),
            _node(node_id="op:B", op_code="B001_20", seq=20),
            _node(node_id="op:C", op_code="B001_30", seq=30),
        ],
        [
            _edge(from_node_id="op:A", to_node_id="op:B"),
            _edge(from_node_id="op:B", to_node_id="op:C"),
        ],
    )

    assert get_topological_order(graph) == ["op:A", "op:B", "op:C"]
    assert get_generation_index(graph) == {"op:A": 0, "op:B": 1, "op:C": 2}


def test_parallel_generation_uses_stable_sort_key() -> None:
    from core.services.scheduler.graph.metrics import get_generation_index, get_topological_generations

    graph = build_precedence_graph(
        [
            _node(node_id="op:C", op_code="B001_20", seq=20),
            _node(node_id="op:b", op_code="B001_B", seq=10),
            _node(node_id="op:a", op_code="B001_A", seq=10),
        ],
        [
            _edge(from_node_id="op:a", to_node_id="op:C"),
            _edge(from_node_id="op:b", to_node_id="op:C"),
        ],
    )

    assert get_topological_generations(graph) == [["op:a", "op:b"], ["op:C"]]
    assert get_generation_index(graph) == {"op:a": 0, "op:b": 0, "op:C": 1}


def test_cycle_topology_exposes_networkx_unfeasible() -> None:
    from core.services.scheduler.graph.metrics import get_topological_order
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
        get_topological_order(graph)


@pytest.mark.parametrize("field_name", ["batch_id", "seq", "op_code"])
def test_topology_sort_key_requires_builder_node_fields(field_name: str) -> None:
    from core.services.scheduler.graph.metrics import get_topological_order

    graph = build_precedence_graph(
        [
            _node(node_id="op:A", op_code="B001_10", seq=10),
            _node(node_id="op:B", op_code="B001_20", seq=20),
        ],
        [],
    )
    del graph.nodes["op:A"][field_name]

    with pytest.raises(KeyError, match=field_name):
        get_topological_order(graph)


def test_metrics_module_does_not_import_upper_graph_layers() -> None:
    forbidden_modules = [
        "core.services.scheduler.graph.validators",
        "core.services.scheduler.graph.analysis_service",
        "core.services.scheduler.graph.exporter",
        "core.services.scheduler.graph.ready_queue",
        "core.services.scheduler.graph.scoring",
        "core.services.scheduler.run.schedule_orchestrator",
    ]
    sys.modules.pop("core.services.scheduler.graph.metrics", None)
    for module_name in forbidden_modules:
        sys.modules.pop(module_name, None)

    importlib.import_module("core.services.scheduler.graph.metrics")

    assert [module_name for module_name in forbidden_modules if module_name in sys.modules] == []
