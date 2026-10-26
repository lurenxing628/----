"""Order moves of the iterated greedy stage: parent extraction, parking removed operations, insertion ranks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core.errors import ValidationError

from .repair_decisions import RepairParentPreparation


@dataclass(frozen=True)
class _Parent:
    order: Tuple[int, ...]
    batch_order: Tuple[str, ...]
    inherited: Tuple[Tuple[int, str, str], ...]
    prepared: RepairParentPreparation

    @property
    def predecessors(self) -> Dict[int, Set[int]]:
        return self.prepared.predecessors

    @property
    def successors(self) -> Dict[int, Set[int]]:
        return self.prepared.successors


def _parent_from_candidate(candidate: Dict[str, Any], *, graph_context: Dict[str, Any],
                           prepared: RepairParentPreparation) -> Optional[_Parent]:
    """``prepared`` is the candidate's parent preparation (EliteRepairPool.prepare_parent)."""
    if candidate["summary"].failed_ops or not candidate["summary"].success:
        return None
    mutable = prepared.mutable_operation_ids
    if not mutable or set(prepared.decoded_rows) != mutable:
        return None
    if mutable.intersection(graph_context.get("fixed_op_ids", ())):
        raise ValidationError("GraphReady 迭代贪心的可变范围不能包含固定工序。", field="graph_ready_iterated_greedy",
                              details={"reason": "graph_ready_ig_scope_mismatch"})
    batch_order = tuple(batch for batch in prepared.decoded_batch_order if batch in prepared.mutable_batch_ids)
    if set(batch_order) != prepared.mutable_batch_ids:
        return None
    return _Parent(prepared.operation_order, batch_order, prepared.inherited_resources, prepared)


def _park(order: Tuple[int, ...], removed: Set[int], *, successors: Dict[int, Set[int]]) -> List[int]:
    """Kept operations keep their order; removed ones are parked at their latest feasible rank.

    Removed operations are inserted successors-first (reverse topological order), so an
    operation whose successor was also removed still lands ahead of that successor.
    """
    working = [op_id for op_id in order if op_id not in removed]
    for op_id in reversed(order):
        if op_id in removed:
            working.insert(_latest_rank(working, successors=successors[op_id]), op_id)
    return working


def _latest_rank(working: List[int], *, successors: Set[int]) -> int:
    """Park a removed operation just before its first successor, or at the end."""
    return next((position for position, item in enumerate(working) if item in successors), len(working))


def _insertion_positions(without: List[int], op_id: int, *, parent: _Parent, anchor: int, window: int,
                         explore: bool = False) -> List[int]:
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
    if explore:
        for position in (low, (low + high) // 2, high):
            if position not in positions:
                positions.append(position)
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
