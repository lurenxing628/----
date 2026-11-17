from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set, Tuple

from core.algorithm_contracts.value_domains import INTERNAL

from .id_policy import display_id, make_machine_node_id
from .nx_runtime import import_networkx
from .types import OperationGraphNode

_DIAGNOSTIC_SAMPLE_LIMIT = 50


@dataclass(frozen=True)
class OperationMachineMatch:
    operation_node_id: str
    machine_node_id: str
    operation_id: str
    machine_id: str


@dataclass(frozen=True)
class ResourceMatchingSummary:
    status: str
    reason: str
    ready_operation_count: int
    operation_with_candidate_count: int
    machine_count: int
    edge_count: int
    matched_operation_count: int
    unmatched_operation_ids: Tuple[str, ...] = field(default_factory=tuple)
    bottleneck_machine_ids: Tuple[str, ...] = field(default_factory=tuple)
    matches: Tuple[OperationMachineMatch, ...] = field(default_factory=tuple)
    warnings: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)


def _node_display_id(node: OperationGraphNode) -> str:
    return display_id(node.node_id)


def _missing_candidate_warning(node: OperationGraphNode) -> Dict[str, Any]:
    return {
        "code": "graph_resource_no_candidate_machine",
        "message": "ready 工序没有 candidate_machine_ids，资源匹配不会回退成全量设备。",
        "data": {
            "operation_id": _node_display_id(node),
            "operation_node_id": str(node.node_id),
        },
    }


def _build_operation_machine_graph(
    ready_nodes: List[OperationGraphNode],
) -> Tuple[Any, Tuple[str, ...], Dict[str, Set[str]], Dict[str, int], Tuple[Dict[str, Any], ...]]:
    # 匹配图节点用整数：工序按就绪次序编 0..n-1，设备按编号排序接在其后。Hopcroft-Karp 按集合次序遍历工序侧，
    # 字符串节点的集合次序随 PYTHONHASHSEED 变化，存在多个最大匹配时选中哪一个会跨进程漂移；整数哈希与种子无关。
    nx = import_networkx()
    operation_count = len(ready_nodes)
    machine_ids = sorted({machine_id for node in ready_nodes for machine_id in node.candidate_machine_ids})
    machine_index_by_id = {machine_id: operation_count + offset for offset, machine_id in enumerate(machine_ids)}
    graph = nx.Graph()
    graph.add_nodes_from(range(operation_count))
    candidate_machine_ids_by_operation: Dict[str, Set[str]] = {}
    machine_edge_counts: Dict[str, int] = {}
    warnings: List[Dict[str, Any]] = []

    for operation_index, node in enumerate(ready_nodes):
        operation_machine_ids = set(node.candidate_machine_ids)
        candidate_machine_ids_by_operation[str(node.node_id)] = operation_machine_ids
        if not operation_machine_ids:
            warnings.append(_missing_candidate_warning(node))
            continue
        for machine_id in sorted(operation_machine_ids):
            graph.add_edge(operation_index, machine_index_by_id[machine_id])
            machine_edge_counts[machine_id] = int(machine_edge_counts.get(machine_id, 0)) + 1

    machine_node_ids = tuple(make_machine_node_id(machine_id) for machine_id in machine_ids)
    return graph, machine_node_ids, candidate_machine_ids_by_operation, machine_edge_counts, tuple(warnings)


def _operation_matches(
    *,
    raw_matching: Dict[int, int],
    ready_nodes: List[OperationGraphNode],
    machine_node_ids: Tuple[str, ...],
) -> Tuple[OperationMachineMatch, ...]:
    operation_count = len(ready_nodes)
    matches: List[OperationMachineMatch] = []
    for operation_index, node in enumerate(ready_nodes):
        if operation_index not in raw_matching:
            continue
        operation_node_id = str(node.node_id)
        machine_node_id = machine_node_ids[raw_matching[operation_index] - operation_count]
        matches.append(
            OperationMachineMatch(
                operation_node_id=operation_node_id,
                machine_node_id=machine_node_id,
                operation_id=display_id(operation_node_id),
                machine_id=display_id(machine_node_id),
            )
        )
    return tuple(matches)


def _unmatched_operation_ids(
    *,
    ready_nodes: List[OperationGraphNode],
    matched_operation_node_ids: Set[str],
) -> Tuple[str, ...]:
    return tuple(
        _node_display_id(node)
        for node in ready_nodes
        if str(node.node_id) not in matched_operation_node_ids
    )


def _bottleneck_machine_ids(
    *,
    ready_nodes: List[OperationGraphNode],
    matched_operation_node_ids: Set[str],
    candidate_machine_ids_by_operation: Dict[str, Set[str]],
    machine_edge_counts: Dict[str, int],
) -> Tuple[str, ...]:
    unmatched_candidate_machine_ids: Set[str] = set()
    for node in ready_nodes:
        operation_node_id = str(node.node_id)
        if operation_node_id in matched_operation_node_ids:
            continue
        unmatched_candidate_machine_ids.update(candidate_machine_ids_by_operation.get(operation_node_id, set()))
    bottlenecks = [
        (int(machine_edge_counts[machine_id]), machine_id)
        for machine_id in unmatched_candidate_machine_ids
        if int(machine_edge_counts.get(machine_id, 0)) > 1
    ]
    bottlenecks.sort(key=lambda item: (-int(item[0]), str(item[1])))
    return tuple(machine_id for _edge_count, machine_id in bottlenecks)


def summarize_operation_machine_matching(
    ready_nodes: Iterable[OperationGraphNode],
) -> ResourceMatchingSummary:
    """Return report-only maximum matching summary for first-wave ready operations."""
    nodes = [node for node in ready_nodes if node.source == INTERNAL]
    if not nodes:
        return ResourceMatchingSummary(
            status="empty",
            reason="empty_ready_set",
            ready_operation_count=0,
            operation_with_candidate_count=0,
            machine_count=0,
            edge_count=0,
            matched_operation_count=0,
        )

    (
        graph,
        machine_node_ids,
        candidate_machine_ids_by_operation,
        machine_edge_counts,
        warnings,
    ) = _build_operation_machine_graph(nodes)
    raw_matching = import_networkx().bipartite.maximum_matching(graph, top_nodes=range(len(nodes)))
    matches = _operation_matches(raw_matching=raw_matching, ready_nodes=nodes, machine_node_ids=machine_node_ids)
    matched_operation_node_ids = {match.operation_node_id for match in matches}
    unmatched_ids = _unmatched_operation_ids(
        ready_nodes=nodes,
        matched_operation_node_ids=matched_operation_node_ids,
    )
    bottleneck_ids = _bottleneck_machine_ids(
        ready_nodes=nodes,
        matched_operation_node_ids=matched_operation_node_ids,
        candidate_machine_ids_by_operation=candidate_machine_ids_by_operation,
        machine_edge_counts=machine_edge_counts,
    )

    return ResourceMatchingSummary(
        status="available",
        reason="ok",
        ready_operation_count=len(nodes),
        operation_with_candidate_count=sum(1 for node in nodes if bool(node.candidate_machine_ids)),
        machine_count=len(machine_edge_counts),
        edge_count=int(graph.number_of_edges()),
        matched_operation_count=len(matches),
        unmatched_operation_ids=unmatched_ids,
        bottleneck_machine_ids=bottleneck_ids,
        matches=matches,
        warnings=warnings,
    )


def resource_matching_summary_to_public_dict(summary: ResourceMatchingSummary) -> Dict[str, Any]:
    """Return small result_summary.algo.graph_analysis.resource_matching payload."""
    return {
        "status": str(summary.status),
        "reason": str(summary.reason),
        "ready_operation_count": int(summary.ready_operation_count),
        "operation_with_candidate_count": int(summary.operation_with_candidate_count),
        "machine_count": int(summary.machine_count),
        "edge_count": int(summary.edge_count),
        "matched_operation_count": int(summary.matched_operation_count),
        "unmatched_operation_count": len(summary.unmatched_operation_ids),
        "bottleneck_machine_count": len(summary.bottleneck_machine_ids),
    }


def _truncated(values: Tuple[Any, ...], limit: int) -> bool:
    return len(values) > int(limit)


def resource_matching_summary_to_diagnostics_dict(summary: ResourceMatchingSummary) -> Dict[str, Any]:
    """Return sampled diagnostics payload; never returns nx.Graph."""
    matches = summary.matches
    unmatched_operation_ids = summary.unmatched_operation_ids
    bottleneck_machine_ids = summary.bottleneck_machine_ids
    warnings = summary.warnings
    return {
        "matches_sample": [
            {
                "operation_id": match.operation_id,
                "machine_id": match.machine_id,
            }
            for match in matches[:_DIAGNOSTIC_SAMPLE_LIMIT]
        ],
        "matches_count": len(matches),
        "matches_truncated": _truncated(matches, _DIAGNOSTIC_SAMPLE_LIMIT),
        "unmatched_operation_ids_sample": list(unmatched_operation_ids[:_DIAGNOSTIC_SAMPLE_LIMIT]),
        "unmatched_operation_count": len(unmatched_operation_ids),
        "unmatched_operation_ids_truncated": _truncated(unmatched_operation_ids, _DIAGNOSTIC_SAMPLE_LIMIT),
        "bottleneck_machine_ids_sample": list(bottleneck_machine_ids[:_DIAGNOSTIC_SAMPLE_LIMIT]),
        "bottleneck_machine_count": len(bottleneck_machine_ids),
        "bottleneck_machine_ids_truncated": _truncated(bottleneck_machine_ids, _DIAGNOSTIC_SAMPLE_LIMIT),
        "warnings_sample": list(warnings[:_DIAGNOSTIC_SAMPLE_LIMIT]),
        "warning_count": len(warnings),
        "warnings_truncated": _truncated(warnings, _DIAGNOSTIC_SAMPLE_LIMIT),
    }


__all__ = [
    "OperationMachineMatch",
    "ResourceMatchingSummary",
    "resource_matching_summary_to_diagnostics_dict",
    "resource_matching_summary_to_public_dict",
    "summarize_operation_machine_matching",
]
