"""Bounded operation priorities derived from decoded resource timelines.

These are decisions for SGS, never constructed schedule times. Fixed operations
remain in the graph and only mutable nodes can change priority.
"""
from __future__ import annotations

import heapq
from datetime import datetime
from itertools import chain, zip_longest
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .repair_decisions import RepairDecision, RepairParentPreparation, prepare_repair_parent
from .repair_decisions import decoded_topological_order as _decoded_topological_order
from .repair_decisions import resource_timelines as _resource_timelines


def operation_repair_decisions(
    candidate: Dict[str, Any], *, operations: List[Any], graph_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]], batch_order: Tuple[str, ...],
    start_dt: datetime, objective_name: str, limit: int = 8, resource_pool: Optional[Dict[str, Any]] = None,
    prepared_parent: Optional[RepairParentPreparation] = None,
) -> Iterator[Tuple[str, RepairDecision]]:
    prepared = (prepared_parent if prepared_parent is not None
                else prepare_repair_parent(candidate, operations, resource_pool, graph_context))
    if not prepared.operation_order:
        return
    moves = _operation_moves(prepared.resource_timelines, prepared.decoded_rows, metrics_by_op_id, start_dt, objective_name,
                             latest_end_time=prepared.latest_end_time)
    for kind, decision_order in _bounded_operation_orders(
            prepared.operation_order, prepared.operation_ranks, prepared.predecessors, moves, limit):
        yield kind, RepairDecision(batch_order, decision_order, prepared.inherited_resources)


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
        # Rejected DAG moves cost O(nodes + edges), too. Bound attempts as well
        # as outputs; a long precedence chain must not trigger quadratic probes.
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
        changed = list(order)
        changed.remove(source)
        changed.insert(changed.index(target), source)
        decision_order = tuple(changed)
        if decision_order in seen or not _is_topological(decision_order, predecessors):
            continue
        seen.add(decision_order)
        emitted += 1
        yield kind, decision_order


# Public names for other decision stages; the internal helpers stay patchable under their old names.
decoded_topological_order = _decoded_topological_order


def _operation_moves(timelines: List[List[Any]], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                     start_dt: datetime, objective_name: str, *, latest_end_time: Optional[datetime] = None
                     ) -> Iterator[Tuple[str, int, int]]:
    latest = latest_end_time if latest_end_time is not None else max(row.end_time for row in rows.values())
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
                          latest: datetime, objective_name: str) -> Iterator[Tuple[str, int, int]]:
    for left, right in zip(timeline, timeline[1:]):
        left_id, right_id = int(left.op_id), int(right.op_id)
        if left_id not in rows or right_id not in rows:
            continue
        if _is_critical_block_pair(left, right, (left_id, right_id), metrics, latest, objective_name):
            yield "critical_block_swap", right_id, left_id


def _is_critical_block_pair(left: Any, right: Any, ids: Tuple[int, int], metrics: Dict[int, Dict[str, Any]],
                            latest: datetime, objective_name: str) -> bool:
    touches = left.end_time == right.start_time
    critical_signal = any(bool(metrics[op_id].get("is_on_critical_path")) for op_id in ids)
    changeover_signal = objective_name == "min_changeover" and (
        str(getattr(left, "op_type_name", "") or "").strip() != str(getattr(right, "op_type_name", "") or "").strip())
    return touches and (critical_signal or right.end_time == latest or changeover_signal)


def _time_insert_moves(timeline: List[Any], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                       start_dt: datetime, objective_name: str) -> Iterator[Tuple[str, int, int]]:
    ranked = heapq.nsmallest(3, (row for row in timeline if int(row.op_id) in rows),
                            key=lambda row: _target_priority(row, metrics[int(row.op_id)], start_dt, objective_name))
    for target in ranked:
        previous_end = start_dt
        for anchor in timeline:
            if anchor.start_time >= target.start_time:
                break
            if previous_end < anchor.start_time:
                yield "operation_time_insert", int(target.op_id), int(anchor.op_id)
            previous_end = max(previous_end, anchor.end_time)


def _target_priority(row: Any, metric: Dict[str, Any], start_dt: datetime, objective_name: str) -> Tuple[Any, ...]:
    finish = (row.end_time - start_dt).total_seconds() / 3600.0
    tardy = max(finish - float(metric.get("due_deadline_hours", 1e9)), 0.0)
    if objective_name == "min_weighted_tardiness":
        return (-float(metric.get("weighted_due_pressure", metric.get("due_pressure", 0.0))), -tardy, int(row.op_id))
    return (-tardy, -float(metric.get("due_pressure", 0.0)), -finish, int(row.op_id))


def _is_topological(order: Tuple[int, ...], predecessors: Dict[int, set]) -> bool:
    positions = {op_id: index for index, op_id in enumerate(order)}
    return all(positions[parent] < positions[op_id] for op_id, parents in predecessors.items() for parent in parents)
