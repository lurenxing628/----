from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from itertools import zip_longest
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from core.errors import ValidationError

if TYPE_CHECKING:
    from .repair_decisions import RepairParentPreparation


@dataclass(frozen=True)
class RepairNeighborhood:
    order: Tuple[str, ...]
    moves: Tuple[Tuple[str, int, int], ...]


def build_repair_neighborhood(
    *, operations: List[Any], metrics_by_op_id: Dict[int, Dict[str, Any]],
    start_dt: datetime, seed: int, prepared_parent: RepairParentPreparation, objective_name: str = "min_overdue",
) -> RepairNeighborhood:
    mutable_batches = prepared_parent.mutable_batch_ids
    order = tuple(batch for batch in prepared_parent.decoded_batch_order if batch in mutable_batches)
    if len(order) != len(set(order)) or set(order) != mutable_batches:
        raise ValidationError(
            "GraphReady repair 的已解码批次与可变范围不一致。", field="graph_ready_elite_repair",
            details={"reason": "graph_ready_repair_scope_mismatch"},
        )
    signals = _batch_signals(operations=operations, metrics_by_op_id=metrics_by_op_id, start_dt=start_dt,
                            prepared_parent=prepared_parent)
    risky = _risky_batch_indices(order, signals, objective_name=objective_name)
    swaps = _adjacent_swap_moves(len(order), risky, seed=seed)
    inserts = _single_insert_moves(len(order), risky)
    boundary = _boundary_moves(order, signals)
    moves = tuple(move for group in zip_longest(swaps, inserts, boundary) for move in group if move is not None)
    return RepairNeighborhood(order=order, moves=moves)


def _risky_batch_indices(order: Tuple[str, ...], signals: Dict[str, Dict[str, float]],
                        *, objective_name: str = "min_overdue") -> List[int]:
    if objective_name == "min_weighted_tardiness":
        return sorted(range(len(order)), key=lambda i: (-signals[order[i]]["weighted_due_pressure"],
                                                        -signals[order[i]]["tardy"], i))[:3]
    if objective_name == "min_changeover":
        return sorted(range(len(order)), key=lambda i: (-signals[order[i]]["changeovers"],
                                                        -signals[order[i]]["tardy"], i))[:3]
    risky = sorted(range(len(order)), key=lambda i: (
        -signals[order[i]]["tardy"], -signals[order[i]]["due_pressure"],
        -signals[order[i]]["critical"], i,
    ))
    return [i for i in risky if any(signals[order[i]][key] > 0 for key in ("tardy", "due_pressure", "critical"))][:3]


def _adjacent_swap_moves(size: int, risky: List[int], *, seed: int) -> List[Tuple[str, int, int]]:
    adjacent = list(range(max(size - 1, 0)))
    random.Random(int(seed)).shuffle(adjacent)
    adjacent.sort(key=lambda i: not (i in risky or i + 1 in risky))
    return [("adjacent_swap", i, i + 1) for i in adjacent]


def _single_insert_moves(size: int, risky: List[int]) -> List[Tuple[str, int, int]]:
    return [("single_insert", i, j) for i in risky
            for j in sorted({0, max(i - 2, 0), min(i + 2, size - 1), size - 1}) if i != j]


def _batch_signals(
    *, operations: List[Any], metrics_by_op_id: Dict[int, Dict[str, Any]], start_dt: datetime,
    prepared_parent: RepairParentPreparation,
) -> Dict[str, Dict[str, float]]:
    ends = {batch: max((end - start_dt).total_seconds() / 3600.0, 0.0)
            for batch, end in prepared_parent.batch_end_times.items()}
    signals: Dict[str, Dict[str, float]] = {}
    for op in operations:
        batch = str(op.batch_id)
        metric = metrics_by_op_id[int(op.id)]
        row = signals.get(batch)
        if row is None:
            row = {key: 0.0 for key in (
                "tardy", "due_pressure", "critical", "saveability", "sacrifice", "weighted_due_pressure", "changeovers")}
            signals[batch] = row
        row["tardy"] = max(row["tardy"], ends.get(batch, 0.0) - float(metric["due_deadline_hours"]))
        for target, source in (("due_pressure", "due_pressure"), ("saveability", "saveability"), ("sacrifice", "sacrifice_penalty")):
            row[target] = max(row[target], float(metric[source]))
        row["critical"] = max(row["critical"], float(metric["is_on_critical_path"]))
        row["weighted_due_pressure"] = max(row["weighted_due_pressure"], float(metric["weighted_due_pressure"]))
    for batch, row in signals.items():
        row["changeovers"] = prepared_parent.changeovers_by_batch.get(batch, 0.0)
    return signals


def _boundary_moves(order: Tuple[str, ...], signals: Dict[str, Dict[str, float]]) -> List[Tuple[str, int, int]]:
    tardy = [i for i, batch in enumerate(order) if signals[batch]["tardy"] > 0]
    if not tardy:
        return []
    boundary = tardy[0]
    saveable = max(tardy, key=lambda i: (signals[order[i]]["saveability"], -i))
    sacrifice = max(range(len(order)), key=lambda i: (signals[order[i]]["sacrifice"], -i))
    return [("tardy_boundary_move", i, j) for i, j in
            ((saveable, max(boundary - 1, 0)), (sacrifice, len(order) - 1)) if i != j]
