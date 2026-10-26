"""Bounded operation priorities derived from decoded resource timelines.

These are decisions for SGS, never constructed schedule times. Fixed operations
remain in the graph and only mutable nodes can change priority.
"""
from __future__ import annotations

import heapq
from datetime import datetime
from itertools import chain, zip_longest
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.algorithm_contracts.changeover_events import type_transition

from .repair_decisions import RepairDecision, RepairParentPreparation

# Operation moves offered per decoded parent.
_OPERATION_DECISION_LIMIT = 8


def operation_repair_decisions(
    *, metrics_by_op_id: Dict[int, Dict[str, Any]], batch_order: Tuple[str, ...],
    start_dt: datetime, objective_name: str, prepared_parent: RepairParentPreparation,
) -> Iterator[Tuple[str, RepairDecision]]:
    if not prepared_parent.operation_order:
        return
    # A non-empty decoded order has decoded rows, so the parent's latest end time is known.
    moves = _operation_moves(
        prepared_parent.resource_timelines, prepared_parent.decoded_rows, metrics_by_op_id, start_dt, objective_name,
        latest=prepared_parent.latest_end_time)
    for kind, decision_order in _bounded_operation_orders(
            prepared_parent.operation_order, prepared_parent.operation_ranks, prepared_parent.predecessors, moves,
            _OPERATION_DECISION_LIMIT):
        yield kind, RepairDecision(batch_order, decision_order, prepared_parent.inherited_resources)


def _bounded_operation_orders(
    order: Tuple[int, ...], ranks: Dict[int, int], predecessors: Dict[int, set],
    moves: Iterator[Tuple[str, int, int]], limit: int,
) -> Iterator[Tuple[str, Tuple[int, ...]]]:
    """Limit all inspected moves, including duplicate or invalid DAG positions."""
    seen = {order}
    considered_moves = set()
    emitted = 0
    inspected = 0
    moves = iter(moves)
    while emitted < limit and inspected < limit * 4:
        # Bound attempts as well as outputs; a long precedence chain must not trigger quadratic probes.
        try:
            kind, source, target = next(moves)
        except StopIteration:
            break
        inspected += 1
        if (source, target) in considered_moves:
            continue
        considered_moves.add((source, target))
        if source not in ranks or target not in ranks or source == target:
            continue
        src_idx, tgt_idx = ranks[source], ranks[target]
        insert_idx = tgt_idx - int(src_idx < tgt_idx)
        if insert_idx == src_idx:
            continue
        if insert_idx < src_idx:
            if any(ranks.get(parent, -1) >= insert_idx for parent in predecessors.get(source, ())):
                continue
            decision_order = order[:insert_idx] + (source,) + order[insert_idx:src_idx] + order[src_idx + 1:]
        else:
            if any(source in predecessors.get(order[idx], ()) for idx in range(src_idx + 1, insert_idx + 1)):
                continue
            decision_order = order[:src_idx] + order[src_idx + 1:insert_idx + 1] + (source,) + order[insert_idx + 1:]
        if decision_order in seen:
            continue
        seen.add(decision_order)
        emitted += 1
        yield kind, decision_order


def _operation_moves(timelines: List[List[Any]], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                     start_dt: datetime, objective_name: str, *, latest: Optional[datetime]
                     ) -> Iterator[Tuple[str, int, int]]:
    critical = chain.from_iterable(_critical_block_moves(timeline, rows, metrics, latest, objective_name)
                                  for timeline in timelines)
    inserts = chain.from_iterable(_time_insert_moves(timeline, rows, metrics, start_dt, objective_name)
                                 for timeline in timelines)
    # Neither family monopolizes the bounded operation prefix.
    for group in zip_longest(critical, inserts):
        for move in group:
            if move is not None:
                yield move


def _critical_block_moves(timeline: List[Any], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                          latest: Optional[datetime], objective_name: str) -> Iterator[Tuple[str, int, int]]:
    for left, right in zip(timeline, timeline[1:]):
        left_id, right_id = left.op_id, right.op_id
        if left_id not in rows or right_id not in rows:
            continue
        if _is_critical_block_pair(left, right, (left_id, right_id), metrics, latest, objective_name):
            yield "critical_block_swap", right_id, left_id


def _is_critical_block_pair(left: Any, right: Any, ids: Tuple[int, int], metrics: Dict[int, Dict[str, Any]],
                            latest: Optional[datetime], objective_name: str) -> bool:
    touches = left.end_time == right.start_time
    critical_signal = any(bool(metrics[op_id].get("is_on_critical_path")) for op_id in ids)
    same_machine = left.machine_id is not None and left.machine_id == right.machine_id
    nonzero_duration = left.start_time < left.end_time and right.start_time < right.end_time
    changeover_signal = (
        objective_name == "min_changeover"
        and same_machine
        and nonzero_duration
        and type_transition(left.op_type_id, right.op_type_id, ids[0], ids[1]) == 1
    )
    return touches and (critical_signal or right.end_time == latest or changeover_signal)


def _time_insert_moves(timeline: List[Any], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                       start_dt: datetime, objective_name: str) -> Iterator[Tuple[str, int, int]]:
    ranked = heapq.nsmallest(3, (row for row in timeline if row.op_id in rows),
                            key=lambda row: _target_priority(row, metrics[row.op_id], start_dt, objective_name))
    for target in ranked:
        previous_end = start_dt
        for anchor in timeline:
            if anchor.start_time >= target.start_time:
                break
            if previous_end < anchor.start_time:
                yield "operation_time_insert", target.op_id, anchor.op_id
            previous_end = max(previous_end, anchor.end_time)


def _target_priority(row: Any, metric: Dict[str, Any], start_dt: datetime, objective_name: str) -> Tuple[Any, ...]:
    finish = (row.end_time - start_dt).total_seconds() / 3600.0
    tardy = max(finish - float(metric.get("due_deadline_hours", 1e9)), 0.0)
    if objective_name == "min_weighted_tardiness":
        return (-float(metric.get("weighted_due_pressure", metric.get("due_pressure", 0.0))), -tardy, row.op_id)
    return (-tardy, -float(metric.get("due_pressure", 0.0)), -finish, row.op_id)
