"""Order moves of the iterated greedy stage: parent extraction, parking removed operations, insertion ranks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_candidate_payload import decoded_batch_order
from .optimizer_graph_ready_operation_neighbors import decoded_topological_order


@dataclass(frozen=True)
class _Parent:
    order: Tuple[int, ...]
    batch_order: Tuple[str, ...]
    inherited: Tuple[Tuple[int, str, str], ...]
    predecessors: Dict[int, Set[int]]
    successors: Dict[int, Set[int]]


def _parent_from_candidate(candidate: Optional[Dict[str, Any]], *, operations: List[Any],
                           graph_context: Dict[str, Any]) -> Optional[_Parent]:
    if candidate is None or candidate["summary"].failed_ops or not candidate["summary"].success:
        return None
    mutable = {int(op.id) for op in operations}
    rows = {int(row.op_id): row for row in candidate["results"] if int(row.op_id) in mutable}
    if not mutable or set(rows) != mutable:
        return None
    if mutable.intersection(graph_context.get("fixed_op_ids", ())):
        raise ValidationError("GraphReady 迭代贪心的可变范围不能包含固定工序。", field="graph_ready_iterated_greedy",
                              details={"reason": "graph_ready_ig_scope_mismatch"})
    predecessors = _mutable_links(graph_context, mutable, "predecessor_op_ids_by_op_id")
    successors = _mutable_links(graph_context, mutable, "successor_op_ids_by_op_id")
    mutable_batches = {str(op.batch_id) for op in operations}
    batch_order = tuple(batch for batch in decoded_batch_order(candidate["results"]) if batch in mutable_batches)
    if set(batch_order) != mutable_batches:
        return None
    inherited = tuple(tuple(item) for item in candidate.get("repair_decision", {}).get("resource_overrides", ()))
    return _Parent(decoded_topological_order(rows, predecessors), batch_order, inherited, predecessors, successors)


def _mutable_links(graph_context: Dict[str, Any], mutable: Set[int], field: str) -> Dict[int, Set[int]]:
    """Keep only links whose two endpoints belong to this mutable operation scope."""
    return {op_id: set(graph_context[field].get(op_id, ())) & mutable for op_id in mutable}


def _park(order: Tuple[int, ...], removed: Set[int], *, successors: Dict[int, Set[int]]) -> List[int]:
    """Kept operations keep their order; removed ones are parked at their latest feasible rank.

    Removed operations are inserted successors-first (reverse topological order), so an
    operation whose successor was also removed still lands ahead of that successor.
    """
    working = [op_id for op_id in order if op_id not in removed]
    for op_id in reversed(order):
        if op_id in removed:
            working.insert(_latest_rank(working, op_id, successors=successors[op_id]), op_id)
    return working


def _latest_rank(working: List[int], op_id: int, *, successors: Set[int]) -> int:
    """Park a removed operation just before its first successor, or at the end."""
    index = {item: position for position, item in enumerate(working)}
    return min((index[item] for item in successors if item in index), default=len(working))


def _insertion_positions(without: List[int], op_id: int, *, parent: _Parent, anchor: int, window: int) -> List[int]:
    """Ranks between the last predecessor and the first successor, nearest to the old rank first."""
    index = {item: position for position, item in enumerate(without)}
    low = max((index[item] + 1 for item in parent.predecessors[op_id] if item in index), default=0)
    high = min((index[item] for item in parent.successors[op_id] if item in index), default=len(without))
    if low > high:
        raise ValidationError("GraphReady 迭代贪心遇到无法满足前后置关系的工序顺序。", field="graph_ready_iterated_greedy",
                              details={"reason": "graph_ready_ig_cyclic_order"})
    centre = min(max(anchor, low), high)
    positions = [centre]
    _extend_insertion_probes(positions, low=low, high=high, centre=centre, window=window, double_distance=True)
    # Wide windows then take the remaining ranks nearest-first, so a small range is covered completely.
    _extend_insertion_probes(positions, low=low, high=high, centre=centre, window=window, double_distance=False)
    return positions


def _extend_insertion_probes(positions: List[int], *, low: int, high: int, centre: int,
                             window: int, double_distance: bool) -> None:
    """Append lower then upper ranks at each distance, preserving the budget and existing probes."""
    distance = 1
    while len(positions) < window and (centre - distance >= low or centre + distance <= high):
        for position in (centre - distance, centre + distance):
            if low <= position <= high and position not in positions and len(positions) < window:
                positions.append(position)
        distance = distance * 2 if double_distance else distance + 1


__all__ = ["_Parent", "_insertion_positions", "_latest_rank", "_parent_from_candidate", "_park"]
