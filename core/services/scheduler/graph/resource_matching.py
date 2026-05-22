from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set, Tuple

from .id_policy import display_id, make_machine_node_id
from .nx_runtime import import_networkx
from .types import OperationGraphNode

_DIAGNOSTIC_SAMPLE_LIMIT = 50


class GraphResourceMatchingContractError(ValueError):
    pass


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


def _as_ready_node_list(ready_nodes: Iterable[OperationGraphNode]) -> List[OperationGraphNode]:
    nodes = list(ready_nodes)
    seen_node_ids: Set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, OperationGraphNode):
            raise GraphResourceMatchingContractError(
                f"resource_matching 只接受 OperationGraphNode：index={index}"
            )
        node_id = str(node.node_id).strip()
        if node_id in seen_node_ids:
            raise GraphResourceMatchingContractError(f"resource_matching 发现重复 node_id：{node_id}")
        seen_node_ids.add(node_id)
    return nodes


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
) -> Tuple[Any, Set[str], Dict[str, Set[str]], Dict[str, int], Tuple[Dict[str, Any], ...]]:
    nx = import_networkx()
    graph = nx.Graph()
    operation_node_ids: Set[str] = set()
    candidate_machine_ids_by_operation: Dict[str, Set[str]] = {}
    machine_edge_counts: Dict[str, int] = {}
    warnings: List[Dict[str, Any]] = []

    for node in ready_nodes:
        operation_node_id = str(node.node_id)
        operation_node_ids.add(operation_node_id)
        graph.add_node(operation_node_id, bipartite=0)
        machine_ids = {str(machine_id).strip() for machine_id in node.candidate_machine_ids if str(machine_id).strip()}
        candidate_machine_ids_by_operation[operation_node_id] = set(machine_ids)
        if not machine_ids:
            warnings.append(_missing_candidate_warning(node))
            continue
        for machine_id in sorted(machine_ids):
            machine_node_id = make_machine_node_id(machine_id)
            graph.add_node(machine_node_id, bipartite=1)
            graph.add_edge(operation_node_id, machine_node_id)
            machine_edge_counts[machine_id] = int(machine_edge_counts.get(machine_id, 0)) + 1

    return graph, operation_node_ids, candidate_machine_ids_by_operation, machine_edge_counts, tuple(warnings)


def _operation_matches(
    *,
    raw_matching: Dict[Any, Any],
    operation_node_ids: Set[str],
) -> Tuple[OperationMachineMatch, ...]:
    matches: List[OperationMachineMatch] = []
    for operation_node_id in sorted(operation_node_ids):
        machine_node_id = raw_matching.get(operation_node_id)
        if machine_node_id is None:
            continue
        matches.append(
            OperationMachineMatch(
                operation_node_id=operation_node_id,
                machine_node_id=str(machine_node_id),
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
        for machine_id in sorted(unmatched_candidate_machine_ids)
        if int(machine_edge_counts.get(machine_id, 0)) > 1
    ]
    bottlenecks.sort(key=lambda item: (-int(item[0]), str(item[1])))
    return tuple(machine_id for _edge_count, machine_id in bottlenecks)


def summarize_operation_machine_matching(
    ready_nodes: Iterable[OperationGraphNode],
) -> ResourceMatchingSummary:
    """Return report-only maximum matching summary for first-wave ready operations."""
    nodes = _as_ready_node_list(ready_nodes)
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
        operation_node_ids,
        candidate_machine_ids_by_operation,
        machine_edge_counts,
        warnings,
    ) = _build_operation_machine_graph(nodes)
    raw_matching = dict(import_networkx().bipartite.maximum_matching(graph, top_nodes=operation_node_ids))
    matches = _operation_matches(raw_matching=raw_matching, operation_node_ids=operation_node_ids)
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
        ready_operation_count=int(len(nodes)),
        operation_with_candidate_count=sum(1 for node in nodes if bool(node.candidate_machine_ids)),
        machine_count=int(len(machine_edge_counts)),
        edge_count=int(graph.number_of_edges()),
        matched_operation_count=int(len(matches)),
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
        "unmatched_operation_count": int(len(summary.unmatched_operation_ids)),
        "bottleneck_machine_count": int(len(summary.bottleneck_machine_ids)),
    }


def _truncated(values: Tuple[Any, ...], limit: int) -> bool:
    return len(values) > int(limit)


def resource_matching_summary_to_diagnostics_dict(summary: ResourceMatchingSummary) -> Dict[str, Any]:
    """Return sampled diagnostics payload; never returns nx.Graph."""
    matches = tuple(summary.matches)
    unmatched_operation_ids = tuple(summary.unmatched_operation_ids)
    bottleneck_machine_ids = tuple(summary.bottleneck_machine_ids)
    warnings = tuple(summary.warnings)
    return {
        "matches_sample": [
            {
                "operation_id": match.operation_id,
                "machine_id": match.machine_id,
            }
            for match in matches[:_DIAGNOSTIC_SAMPLE_LIMIT]
        ],
        "matches_count": int(len(matches)),
        "matches_truncated": _truncated(matches, _DIAGNOSTIC_SAMPLE_LIMIT),
        "unmatched_operation_ids_sample": list(unmatched_operation_ids[:_DIAGNOSTIC_SAMPLE_LIMIT]),
        "unmatched_operation_count": int(len(unmatched_operation_ids)),
        "unmatched_operation_ids_truncated": _truncated(unmatched_operation_ids, _DIAGNOSTIC_SAMPLE_LIMIT),
        "bottleneck_machine_ids_sample": list(bottleneck_machine_ids[:_DIAGNOSTIC_SAMPLE_LIMIT]),
        "bottleneck_machine_count": int(len(bottleneck_machine_ids)),
        "bottleneck_machine_ids_truncated": _truncated(bottleneck_machine_ids, _DIAGNOSTIC_SAMPLE_LIMIT),
        "warnings_sample": [dict(warning) for warning in warnings[:_DIAGNOSTIC_SAMPLE_LIMIT]],
        "warning_count": int(len(warnings)),
        "warnings_truncated": _truncated(warnings, _DIAGNOSTIC_SAMPLE_LIMIT),
    }


__all__ = [
    "GraphResourceMatchingContractError",
    "OperationMachineMatch",
    "ResourceMatchingSummary",
    "resource_matching_summary_to_diagnostics_dict",
    "resource_matching_summary_to_public_dict",
    "summarize_operation_machine_matching",
]
