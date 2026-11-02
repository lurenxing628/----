from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, Iterator, List, Optional, Tuple

from core.algorithm_contracts.changeover_events import type_transition
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithms.greedy.dispatch.sgs_graph import graph_priority_key_map
from core.errors import ValidationError

if TYPE_CHECKING:
    from core.algorithms.greedy.dispatch.sgs_graph import PreparedGraphReadyTopology
    from core.algorithms.greedy.dispatch.sgs_priority_keys import ValidatedGraphPriorityKeys


@dataclass(frozen=True)
class RepairDecision:
    """One explicit priority decision, always generated from a prepared decoded parent.

    Batch moves, operation moves and resource moves all derive from the parent's own
    decoded facts and qualified pairs, so a decision carries no separate admission.
    """

    batch_order: Tuple[str, ...]
    operation_order: Tuple[int, ...] = ()
    resource_overrides: Tuple[Tuple[int, str, str], ...] = ()


@dataclass(frozen=True)
class PreparedRepairScope:
    operations_by_id: Dict[int, Any]
    mutable_operation_ids: FrozenSet[int]
    mutable_batch_ids: FrozenSet[str]
    predecessors: Dict[int, set]
    successors: Dict[int, set]
    changeable_op_ids: FrozenSet[int]
    changeable_operations: Tuple[Any, ...]
    qualified_pairs_by_op_id: Dict[int, Tuple[Tuple[str, str], ...]]
    resource_pairs_for: Callable[[Any], Tuple[Tuple[str, str], ...]]

    def sorted_pairs_for(self, op: Any) -> Tuple[Tuple[str, str], ...]:
        op_id = op.id
        cached = self.qualified_pairs_by_op_id.get(op_id)
        if cached is None:
            cached = tuple(sorted(self.resource_pairs_for(op)))
            self.qualified_pairs_by_op_id[op_id] = cached
        return cached


@dataclass(frozen=True)
class RepairParentPreparation:
    operations_by_id: Dict[int, Any]
    mutable_operation_ids: FrozenSet[int]
    mutable_batch_ids: FrozenSet[str]
    decoded_rows: Dict[int, Any]
    current_resources: Dict[int, Tuple[Optional[str], Optional[str]]]
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
    scope: PreparedRepairScope


def prepare_repair_scope(
    operations: List[Any],
    topology: PreparedGraphReadyTopology,
    *,
    resource_pairs_for: Callable[[Any], Tuple[Tuple[str, str], ...]],
) -> PreparedRepairScope:
    """``operations`` are exactly the topology's schedulable operations; its id set is shared, not rebuilt."""
    by_id = _operations_by_id(operations)
    mutable = topology.schedulable_ids
    mutable_batches = frozenset(op.batch_id for op in operations)
    predecessors = {op_id: set(topology.predecessors[op_id]) & mutable for op_id in mutable}
    successors = {op_id: set(topology.successors[op_id]) & mutable for op_id in mutable}
    changeable_operations = tuple(op for op in operations if _can_change_resources(op))
    changeable_op_ids = frozenset(op.id for op in changeable_operations)
    return PreparedRepairScope(
        operations_by_id=by_id,
        mutable_operation_ids=mutable,
        mutable_batch_ids=mutable_batches,
        predecessors=predecessors,
        successors=successors,
        changeable_op_ids=changeable_op_ids,
        changeable_operations=changeable_operations,
        qualified_pairs_by_op_id={},
        resource_pairs_for=resource_pairs_for,
    )


def prepare_repair_parent(
    candidate: Dict[str, Any],
    *,
    scope: PreparedRepairScope,
) -> RepairParentPreparation:
    """Prepare the decoded parent's static facts once from the shared repair scope; basis-specific signals remain separate."""
    by_id = scope.operations_by_id
    mutable = scope.mutable_operation_ids
    mutable_batches = scope.mutable_batch_ids
    rows = _decoded_rows(candidate, by_id)
    current = {op_id: (row.machine_id, row.operator_id) for op_id, row in rows.items()}
    inherited = _inherited_resource_rows(current, changeable_op_ids=scope.changeable_op_ids)
    timelines_by_resource = resource_timeline_groups(candidate["results"])
    timelines = list(timelines_by_resource.values())
    batch_ends = {}
    for row in candidate["results"]:
        batch_ends[row.batch_id] = max(batch_ends.get(row.batch_id, row.end_time), row.end_time)
    changeovers = _batch_changeovers(timelines_by_resource, mutable_batches)
    predecessors: Dict[int, set] = {}
    successors: Dict[int, set] = scope.successors
    order: Tuple[int, ...] = ()
    if mutable and set(rows) == mutable:
        predecessors = scope.predecessors
        order = decoded_topological_order(rows, predecessors, successors)
    return RepairParentPreparation(
        operations_by_id=by_id, mutable_operation_ids=mutable, mutable_batch_ids=mutable_batches,
        decoded_rows=rows, current_resources=current, predecessors=predecessors,
        successors=successors, operation_order=order,
        operation_ranks={op_id: index for index, op_id in enumerate(order)}, resource_timelines=timelines,
        batch_end_times=batch_ends, changeovers_by_batch=changeovers,
        latest_end_time=max((row.end_time for row in rows.values()), default=None),
        inherited_resources=inherited, decoded_batch_order=candidate["decoded_batch_order"],
        scope=scope,
    )


def decoded_topological_order(
    rows: Dict[int, Any], predecessors: Dict[int, set], successors: Dict[int, set],
) -> Tuple[int, ...]:
    pending = {op_id: len(parents) for op_id, parents in predecessors.items()}
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
    decision: RepairDecision, prepared_parent: RepairParentPreparation,
) -> Tuple[ValidatedGraphPriorityKeys, Dict[int, Tuple[str, str]]]:
    """The decision's admitted priority keys and resource overrides, read from its prepared parent's facts."""
    overrides = {op_id: (machine, operator) for op_id, machine, operator in decision.resource_overrides}
    ranks = {batch: float(index) for index, batch in enumerate(decision.batch_order)}
    by_id = prepared_parent.operations_by_id
    if decision.operation_order:
        keys = {op_id: (float(rank), ranks[by_id[op_id].batch_id]) for rank, op_id in enumerate(decision.operation_order)}
    else:
        keys = {op_id: (ranks[op.batch_id],) for op_id, op in by_id.items()}
    return graph_priority_key_map(keys, schedulable_ids=prepared_parent.mutable_operation_ids), overrides


# Resource moves offered per decoded parent.
_MAX_RESOURCE_DECISIONS = 8


def iter_resource_decisions(
    *, batch_order: Tuple[str, ...], operation_order: Tuple[int, ...],
    prepared_parent: RepairParentPreparation,
) -> Iterator[RepairDecision]:
    """Yield bounded one-operation moves from a prepared decoded parent, preserving its accepted overrides."""
    current = prepared_parent.current_resources
    inherited = {op_id: (machine, operator) for op_id, machine, operator in prepared_parent.inherited_resources}
    scope = prepared_parent.scope
    generated = 0
    for op in scope.changeable_operations:
        if op.id not in current:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
        if not all(current[op.id]):
            continue  # A point event without a selected pair does not introduce resources.
        for pair in scope.sorted_pairs_for(op):
            if pair == current[op.id]:
                continue
            overrides = dict(inherited)
            overrides[op.id] = pair
            rows = tuple((op_id, values[0], values[1]) for op_id, values in sorted(overrides.items()))
            yield RepairDecision(batch_order, operation_order, rows)
            generated += 1
            if generated >= _MAX_RESOURCE_DECISIONS:
                return


def _operations_by_id(operations: List[OpForScheduleAlgo]) -> Dict[int, OpForScheduleAlgo]:
    return {op.id: op for op in operations}


def _inherited_resource_rows(current, *, changeable_op_ids: FrozenSet[int]):
    return tuple(
        (op_id, machine, operator)
        for op_id, (machine, operator) in sorted(current.items())
        if op_id in changeable_op_ids and machine and operator
    )


def _can_change_resources(op: OpForScheduleAlgo) -> bool:
    return op.source == INTERNAL and not (op.machine_id and op.operator_id)


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


def _invalid(field: str, *, reason: str) -> None:
    raise ValidationError(
        "GraphReady repair 决策无效：" + field, field="graph_ready_elite_repair", details={"reason": reason},
    )
