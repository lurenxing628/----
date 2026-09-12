"""影响数量契约：无分叉图线性计数、一般 DAG 按真实分量精确去重，非法拓扑显式失败。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from core.services.scheduler.graph import impact_counts
from core.services.scheduler.graph.metrics import _compute_impact_counts_by_node, build_node_metrics
from core.services.scheduler.graph.nx_runtime import import_networkx


def _graph(node_count: int, edges: List[Tuple[int, int]]) -> Any:
    graph = import_networkx().DiGraph()
    for node_id in range(node_count):
        graph.add_node(
            str(node_id),
            batch_id="shared-batch",
            seq=node_id,
            op_code=str(node_id),
            duration_minutes=1,
        )
    graph.add_edges_from((str(source), str(target), {"lag_minutes": 0}) for source, target in edges)
    return graph


def _counts_from_reachability(graph: Any) -> Dict[str, int]:
    nx = import_networkx()
    return {node_id: len(nx.descendants(graph, node_id)) for node_id in graph}


@pytest.mark.parametrize(
    "node_count,edges",
    [
        (0, []),
        (4, []),
        (7, [(0, 1), (1, 2), (3, 4)]),
        (4, [(0, 2), (1, 2), (2, 3)]),
        (4, [(0, 1), (0, 2), (0, 3)]),
        (4, [(0, 1), (0, 2), (1, 3), (2, 3)]),
        (6, [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5)]),
    ],
    ids=["empty", "isolated", "independent-chains", "convergence", "fork", "diamond", "reconvergence"],
)
def test_impact_counts_match_reachability(node_count: int, edges: List[Tuple[int, int]]) -> None:
    graph = _graph(node_count, edges)
    nx = import_networkx()
    order = list(nx.topological_sort(graph))
    expected = _counts_from_reachability(graph)

    assert _compute_impact_counts_by_node(graph, order) == expected
    assert {node_id: metric["impact_count"] for node_id, metric in build_node_metrics(graph).items()} == expected


def test_many_short_chains_do_not_build_bitsets(monkeypatch: Any) -> None:
    chain_count, chain_length = 1000, 6
    graph = _graph(
        chain_count * chain_length,
        [
            (chain * chain_length + step, chain * chain_length + step + 1)
            for chain in range(chain_count)
            for step in range(chain_length - 1)
        ],
    )
    # 按层交错排列各条链，复现过去使用全图位下标的扩展性问题。
    order = [
        str(chain * chain_length + step)
        for step in range(chain_length)
        for chain in range(chain_count)
    ]

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("single-successor DAG must not construct component bitsets")

    monkeypatch.setattr(impact_counts, "_compute_component_impact_counts", fail_if_called)
    actual = _compute_impact_counts_by_node(graph, order)

    assert actual == {
        str(chain * chain_length + step): chain_length - step - 1
        for chain in range(chain_count)
        for step in range(chain_length)
    }


def test_converging_paths_without_forks_do_not_build_bitsets(monkeypatch: Any) -> None:
    graph = _graph(5, [(0, 2), (1, 2), (2, 3)])

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("converging single-successor paths are exact without bitsets")

    monkeypatch.setattr(impact_counts, "_compute_component_impact_counts", fail_if_called)

    assert _compute_impact_counts_by_node(graph, ["0", "1", "2", "3", "4"]) == {
        "0": 2, "1": 2, "2": 1, "3": 0, "4": 0,
    }


def test_independent_diamonds_use_only_component_width_bits(monkeypatch: Any) -> None:
    component_count = 80
    edges = [
        (4 * component + source, 4 * component + target)
        for component in range(component_count)
        for source, target in [(0, 1), (0, 2), (1, 3), (2, 3)]
    ]
    graph = _graph(4 * component_count, edges)
    # 同一 batch 包含多个分量，单个分量也跨 batch；不得按批次标签切图。
    for node_id in graph:
        graph.nodes[node_id]["batch_id"] = f"batch-{int(node_id) % 3}"
    order = [str(4 * component + step) for step in range(4) for component in range(component_count)]
    bit_widths: List[int] = []
    original_popcount = impact_counts._popcount

    def counted_popcount(mask: int) -> int:
        bit_widths.append(mask.bit_length())
        return original_popcount(mask)

    monkeypatch.setattr(impact_counts, "_popcount", counted_popcount)
    expected = _counts_from_reachability(graph)

    assert _compute_impact_counts_by_node(graph, order) == expected
    assert len(bit_widths) == 4 * component_count
    assert max(bit_widths) == 4


def test_all_five_node_dags_match_distinct_reachability() -> None:
    possible_edges = [(source, target) for source in range(5) for target in range(source + 1, 5)]
    order = [str(node_id) for node_id in range(5)]
    for edge_mask in range(1 << len(possible_edges)):
        edges = [edge for index, edge in enumerate(possible_edges) if edge_mask & (1 << index)]
        graph = _graph(5, edges)

        assert _compute_impact_counts_by_node(graph, order) == _counts_from_reachability(graph)


@pytest.mark.parametrize(
    "edges,order",
    [
        ([(0, 1)], ["0"]),
        ([(0, 1)], ["1", "0"]),
        ([(0, 0)], ["0", "1", "2"]),
        ([(0, 1), (1, 0)], ["0", "1", "2"]),
        ([(0, 1), (0, 2)], ["0", "1"]),
        ([(0, 1), (0, 2)], ["1", "2", "0"]),
    ],
    ids=["missing-successor", "reversed-chain", "self-cycle", "cycle", "missing-fork-successor", "reversed-fork"],
)
def test_invalid_topological_context_does_not_turn_missing_counts_into_zero(
    edges: List[Tuple[int, int]], order: List[str]
) -> None:
    graph = _graph(3, edges)

    with pytest.raises(KeyError):
        _compute_impact_counts_by_node(graph, order)
