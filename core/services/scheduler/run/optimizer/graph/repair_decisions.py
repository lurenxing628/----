from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, FrozenSet, Iterator, List, Optional, Tuple

from core.algorithm_contracts.changeover_events import type_transition
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithms.greedy.auto_assign import qualified_resource_pairs
from core.errors import ValidationError

from ..shared_decode import resource_pair
from .candidate_payload import decoded_batch_order
from .repair_neighbors import repair_priority_context


@dataclass(frozen=True)
class RepairDecision:
    batch_order: Tuple[str, ...]
    operation_order: Tuple[int, ...] = ()
    resource_overrides: Tuple[Tuple[int, str, str], ...] = ()

    @classmethod
    def _unvalidated(
        cls,
        batch_order: Tuple[str, ...],
        operation_order: Tuple[int, ...] = (),
        resource_overrides: Tuple[Tuple[int, str, str], ...] = (),
    ) -> RepairDecision:
        obj = object.__new__(cls)
        object.__setattr__(obj, "batch_order", batch_order)
        object.__setattr__(obj, "operation_order", operation_order)
        object.__setattr__(obj, "resource_overrides", resource_overrides)
        return obj

    def __post_init__(self) -> None:
        if not isinstance(self.batch_order, tuple) or any(not isinstance(v, str) for v in self.batch_order):
            _invalid("batch_order")
        if not isinstance(self.operation_order, tuple):
            _invalid("operation_order")
        _unique_ids(self.operation_order, field="operation_order")
        if not isinstance(self.resource_overrides, tuple):
            _invalid("resource_overrides")
        ids = []
        for row in self.resource_overrides:
            if not isinstance(row, tuple) or len(row) != 3:
                _invalid("resource_overrides")
            ids.append(row[0])
            if any(not isinstance(v, str) or not v or v != v.strip() for v in row[1:]):
                _invalid("resource_overrides")
        _unique_ids(ids, field="resource_overrides")


@dataclass(frozen=True)
class RepairParentPreparation:
    operations_by_id: Dict[int, Any]
    mutable_operation_ids: FrozenSet[int]
    mutable_batch_ids: FrozenSet[str]
    decoded_rows: Dict[int, Any]
    current_resources: Dict[int, Tuple[str, str]]
    predecessors: Dict[int, set]
    successors: Dict[int, set]
    operation_order: Tuple[int, ...]
    operation_ranks: Dict[int, int]
    resource_timelines: List[List[Any]]
    batch_end_times: Dict[str, datetime]
    changeovers_by_batch: Dict[str, float]
    latest_end_time: Optional[datetime]
    inherited_resources: Tuple[Tuple[int, str, str], ...]
    decoded_batch_order: Tuple[str, ...]
    pool_maps: Optional[Dict[str, Any]]
    resource_pairs_for: Optional[Callable[[Any], Tuple[Tuple[str, str], ...]]]


def prepare_repair_parent(
    candidate: Dict[str, Any], operations: List[Any], resource_pool: Optional[Dict[str, Any]],
    graph_context: Optional[Dict[str, Any]] = None, *, resource_moves: bool = False,
    resource_pairs_for: Optional[Callable[[Any], Tuple[Tuple[str, str], ...]]] = None,
) -> RepairParentPreparation:
    """Prepare the decoded parent's static facts once; basis-specific signals remain separate."""
    by_id = _operations_by_id(operations)
    mutable = frozenset(by_id)
    mutable_batches = frozenset(op.batch_id for op in operations)
    rows = _decoded_rows(candidate, by_id)
    current = {op_id: resource_pair(row) for op_id, row in rows.items()}
    inherited = _inherited_resource_rows(current, by_id)
    pool_maps = _pool_maps(resource_pool) if resource_moves and resource_pairs_for is None else None
    timelines_by_resource = resource_timeline_groups(candidate["results"])
    timelines = list(timelines_by_resource.values())
    batch_ends = {}
    for row in candidate["results"]:
        batch_ends[row.batch_id] = max(batch_ends.get(row.batch_id, row.end_time), row.end_time)
    changeovers = _batch_changeovers(timelines_by_resource, mutable_batches)
    predecessors, order = {}, ()
    if graph_context is not None and mutable and set(rows) == mutable:
        predecessors = {op_id: set(graph_context["predecessor_op_ids_by_op_id"].get(op_id, ())) & mutable
                        for op_id in mutable}
        order = decoded_topological_order(rows, predecessors)
    return RepairParentPreparation(
        operations_by_id=by_id, mutable_operation_ids=mutable, mutable_batch_ids=mutable_batches,
        decoded_rows=rows, current_resources=current, predecessors=predecessors,
        successors={op_id: set(graph_context["successor_op_ids_by_op_id"].get(op_id, ())) & mutable
                    for op_id in mutable} if graph_context is not None else {}, operation_order=order,
        operation_ranks={op_id: index for index, op_id in enumerate(order)}, resource_timelines=timelines,
        batch_end_times=batch_ends, changeovers_by_batch=changeovers,
        latest_end_time=max((row.end_time for row in rows.values()), default=None),
        inherited_resources=inherited, decoded_batch_order=tuple(candidate.get("decoded_batch_order")
                                                               or decoded_batch_order(candidate["results"])),
        pool_maps=pool_maps, resource_pairs_for=resource_pairs_for,
    )


def decoded_topological_order(rows: Dict[int, Any], predecessors: Dict[int, set]) -> Tuple[int, ...]:
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


def resource_timeline_groups(results: List[ScheduleResult]) -> Dict[Tuple[str, str], List[ScheduleResult]]:
    timelines: Dict[Tuple[str, str], List[ScheduleResult]] = defaultdict(list)
    for row in results:
        for field, resource in (("machine_id", row.machine_id), ("operator_id", row.operator_id)):
            if resource is not None:
                timelines[(field, resource)].append(row)
    return {key: sorted(rows, key=lambda row: (row.start_time, row.end_time, row.op_id))
            for key, rows in sorted(timelines.items())}


def _batch_changeovers(timelines: Dict[Tuple[str, str], List[Any]], batches: FrozenSet[str]) -> Dict[str, float]:
    counts: Dict[str, float] = {}
    for (kind, _resource), rows in timelines.items():
        if kind != "machine_id":
            continue
        previous = None
        for row in rows:
            if row.start_time == row.end_time:
                continue
            if previous is not None and type_transition(
                previous.op_type_id, row.op_type_id, previous.op_id, row.op_id,
            ) == 1:
                for changed in (previous, row):
                    if changed.batch_id in batches:
                        counts[changed.batch_id] = counts.get(changed.batch_id, 0.0) + 1.0
            previous = row
    return counts


def repair_decision_inputs(
    context: Dict[str, Any], operations: List[OpForScheduleAlgo], decision: RepairDecision,
    resource_pool: Optional[Dict[str, Any]], *, prepared_parent: Optional[RepairParentPreparation] = None,
) -> Tuple[Dict[str, Any], Dict[int, Tuple[str, str]]]:
    """Admit raw decisions once; generated decisions consume their prepared parent's facts."""
    if prepared_parent is None:
        by_id = _operations_by_id(operations)
        if set(by_id).intersection(context.get("fixed_op_ids", ())):
            _invalid("fixed_op_ids", reason="graph_ready_repair_scope_mismatch")
        if decision.operation_order and set(decision.operation_order) != set(by_id):
            _invalid("operation_order", reason="graph_ready_repair_scope_mismatch")
        overrides = _validated_overrides(decision.resource_overrides, by_id, resource_pool)
        out = repair_priority_context(context, operations=operations, order=list(decision.batch_order))
    else:
        overrides = {op_id: (machine, operator) for op_id, machine, operator in decision.resource_overrides}
        ranks = {batch: float(index) for index, batch in enumerate(decision.batch_order)}
        out = dict(context)
        by_id = prepared_parent.operations_by_id
        if decision.operation_order:
            out["graph_priority_key_by_op_id"] = {
                op_id: (float(rank), ranks[by_id[op_id].batch_id])
                for rank, op_id in enumerate(decision.operation_order)
            }
            return out, overrides
        out["graph_priority_key_by_op_id"] = {
            op_id: (ranks[op.batch_id],) for op_id, op in by_id.items()
        }
        return out, overrides
    if decision.operation_order:
        batch_keys = out["graph_priority_key_by_op_id"]
        out["graph_priority_key_by_op_id"] = {
            op_id: (float(rank),) + batch_keys[op_id]
            for rank, op_id in enumerate(decision.operation_order)
        }
    return out, overrides


def iter_resource_decisions(
    *, operations: List[Any], resource_pool: Optional[Dict[str, Any]], batch_order: Tuple[str, ...],
    operation_order: Tuple[int, ...], prepared_parent: RepairParentPreparation, max_decisions: int = 8,
) -> Iterator[RepairDecision]:
    """Yield bounded one-operation moves from a prepared decoded parent, preserving its accepted overrides."""
    current = prepared_parent.current_resources
    batch_order_tuple, op_order_tuple = tuple(batch_order), tuple(operation_order)
    inherited = {op_id: (machine, operator) for op_id, machine, operator in prepared_parent.inherited_resources}
    resource_pairs_for = prepared_parent.resource_pairs_for
    pool = prepared_parent.pool_maps
    if pool is None and resource_pairs_for is None:
        pool = _pool_maps(resource_pool)
    generated = 0
    for op in operations:
        if not _can_change_resources(op):
            continue
        if op.id not in current:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
        if not all(current[op.id]):
            continue  # A point event without a selected pair does not introduce resources.
        pairs = resource_pairs_for(op) if resource_pairs_for is not None else qualified_resource_pairs(op, pool)
        for pair in sorted(pairs):
            if pair == current[op.id]:
                continue
            overrides = dict(inherited)
            overrides[op.id] = pair
            rows = tuple((op_id, values[0], values[1]) for op_id, values in sorted(overrides.items()))
            yield RepairDecision._unvalidated(batch_order_tuple, op_order_tuple, rows)
            generated += 1
            if generated >= max_decisions:
                return


def _operations_by_id(operations: List[OpForScheduleAlgo]) -> Dict[int, OpForScheduleAlgo]:
    return {op.id: op for op in operations}


def _unique_ids(values: Any, *, field: str) -> None:
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in values):
        _invalid(field)
    if len(values) != len(set(values)):
        _invalid(field)


def _inherited_resource_rows(current, by_id):
    return tuple((op_id, machine, operator) for op_id, (machine, operator) in sorted(current.items())
                 if _can_change_resources(by_id[op_id]) and machine and operator)


def _validated_overrides(
    rows: Tuple[Tuple[int, str, str], ...], by_id: Dict[int, Any], resource_pool: Optional[Dict[str, Any]],
) -> Dict[int, Tuple[str, str]]:
    if not rows:
        return {}
    pool = _pool_maps(resource_pool)
    out = {}
    for op_id, machine_id, operator_id in rows:
        if op_id not in by_id:
            _invalid("resource_overrides", reason="graph_ready_repair_scope_mismatch")
        op = by_id[op_id]
        fixed_machine, fixed_operator = resource_pair(op)
        if (not _can_change_resources(op) or (fixed_machine and machine_id != fixed_machine)
                or (fixed_operator and operator_id != fixed_operator)):
            _invalid("resource_overrides", reason="graph_ready_repair_fixed_resource")
        if (machine_id, operator_id) not in qualified_resource_pairs(op, pool):
            _invalid("resource_overrides", reason="graph_ready_repair_resource_qualification")
        out[op_id] = (machine_id, operator_id)
    return out


def _pool_maps(resource_pool: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if resource_pool is None:
        return {"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}}
    if not isinstance(resource_pool, dict):
        _invalid("resource_pool")
    out = {}
    for key in ("machines_by_op_type", "operators_by_machine", "machines_by_operator"):
        value = resource_pool.get(key, {})
        if not isinstance(value, dict):
            _invalid("resource_pool." + key)
        out[key] = value
    if "operator_skills" in resource_pool:
        out["operator_skills"] = resource_pool["operator_skills"]
    return out


def _can_change_resources(op: OpForScheduleAlgo) -> bool:
    return op.source == INTERNAL and not all(resource_pair(op))


def _decoded_rows(candidate: Dict[str, Any], by_id: Dict[int, OpForScheduleAlgo]) -> Dict[int, Any]:
    out = {}
    for result in candidate["results"]:
        op_id = result.op_id
        if op_id not in by_id:
            continue  # Fixed seed results are outside the mutable decision scope.
        if op_id in out:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
        out[op_id] = result
    return out


def _invalid(field: str, *, reason: str = "graph_ready_repair_bad_decision") -> None:
    raise ValidationError(
        "GraphReady repair 决策无效：" + field, field="graph_ready_elite_repair", details={"reason": reason},
    )
