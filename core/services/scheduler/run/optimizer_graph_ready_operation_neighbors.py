"""Bounded operation priorities derived from decoded resource timelines.

These are decisions for SGS, never constructed schedule times. Fixed operations
remain in the graph and only mutable nodes can change priority.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterator, List, Tuple

from .optimizer_graph_ready_repair_decisions import RepairDecision


def operation_repair_decisions(
    candidate: Dict[str, Any], *, operations: List[Any], graph_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]], batch_order: Tuple[str, ...],
    start_dt: datetime, objective_name: str, limit: int = 8,
) -> Iterator[Tuple[str, RepairDecision]]:
    mutable = {int(op.id) for op in operations}
    rows = {int(row.op_id): row for row in candidate["results"] if int(row.op_id) in mutable}
    if not mutable or set(rows) != mutable:
        return
    predecessors = {op_id: set(graph_context["predecessor_op_ids_by_op_id"].get(op_id, ())) & mutable
                    for op_id in mutable}
    order = _decoded_topological_order(rows, predecessors)
    ranks = {op_id: index for index, op_id in enumerate(order)}
    timelines = _resource_timelines(candidate["results"])
    inherited = tuple(tuple(item) for item in candidate.get("repair_decision", {}).get("resource_overrides", ()))
    moves = _operation_moves(timelines, rows, metrics_by_op_id, start_dt, objective_name)
    for kind, decision_order in _bounded_operation_orders(order, ranks, predecessors, moves, limit):
        yield kind, RepairDecision(batch_order, decision_order, inherited)


def _bounded_operation_orders(
    order: Tuple[int, ...], ranks: Dict[int, int], predecessors: Dict[int, set],
    moves: Iterator[Tuple[str, int, int]], limit: int,
) -> Iterator[Tuple[str, Tuple[int, ...]]]:
    """Limit all inspected moves, including duplicate or invalid DAG positions."""
    seen = {order}
    considered_moves = set()
    emitted = 0
    for inspected, (kind, source, target) in enumerate(moves):
        # Rejected DAG moves cost O(nodes + edges), too. Bound attempts as well
        # as outputs; a long precedence chain must not trigger quadratic probes.
        if emitted >= limit or inspected >= limit * 4:
            break
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


def _decoded_topological_order(rows: Dict[int, Any], predecessors: Dict[int, set]) -> Tuple[int, ...]:
    successors: Dict[int, List[int]] = defaultdict(list)
    pending = {op_id: len(parents) for op_id, parents in predecessors.items()}
    for op_id, parents in predecessors.items():
        for parent in parents:
            successors[parent].append(op_id)
    ready = [(rows[op_id].start_time, rows[op_id].end_time, op_id) for op_id, count in pending.items() if not count]
    heapq.heapify(ready)
    order = []
    while ready:
        _, _, op_id = heapq.heappop(ready)
        order.append(op_id)
        for child in successors[op_id]:
            pending[child] -= 1
            if not pending[child]:
                heapq.heappush(ready, (rows[child].start_time, rows[child].end_time, child))
    if len(order) != len(rows):
        raise ValueError("GraphReady repair cannot reorder a cyclic mutable graph")
    return tuple(order)


def _resource_timelines(results: List[Any]) -> List[List[Any]]:
    timelines: Dict[Tuple[str, str], List[Any]] = defaultdict(list)
    for row in results:
        for field in ("machine_id", "operator_id"):
            resource = str(getattr(row, field, "") or "")
            if resource:
                timelines[(field, resource)].append(row)
    return [sorted(rows, key=lambda row: (row.start_time, row.end_time, int(row.op_id)))
            for _, rows in sorted(timelines.items())]


def _operation_moves(timelines: List[List[Any]], rows: Dict[int, Any], metrics: Dict[int, Dict[str, Any]],
                     start_dt: datetime, objective_name: str) -> Iterator[Tuple[str, int, int]]:
    latest = max(row.end_time for row in rows.values())
    critical = []
    inserts = []
    for timeline in timelines:
        critical.extend(_critical_block_moves(timeline, rows, metrics, latest, objective_name))
        inserts.extend(_time_insert_moves(timeline, rows, metrics, start_dt, objective_name))
    # Neither family monopolizes the bounded operation prefix.
    for index in range(max(len(critical), len(inserts))):
        if index < len(critical):
            yield critical[index]
        if index < len(inserts):
            yield inserts[index]


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
    ranked = sorted((row for row in timeline if int(row.op_id) in rows),
                    key=lambda row: _target_priority(row, metrics[int(row.op_id)], start_dt, objective_name))
    for target in ranked[:3]:
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
