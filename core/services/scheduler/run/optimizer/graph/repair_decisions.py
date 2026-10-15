from __future__ import annotations

import heapq
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Tuple, cast

from core.algorithm_contracts.operator_eligibility import qualified_operators
from core.algorithm_runtime.native_snapshot import make_class_guard
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.services.scheduler.contracts.schedule_input_op import OpForScheduleAlgo

from .candidate_payload import decoded_batch_order
from .repair_neighbors import repair_priority_context

_READONLY_OPERATION_GUARDS = {kind: make_class_guard(kind) for kind in (BatchOperation, OpForScheduleAlgo)}


@dataclass(frozen=True)
class RepairDecision:
    batch_order: Tuple[str, ...]
    operation_order: Tuple[int, ...] = ()
    resource_overrides: Tuple[Tuple[int, str, str], ...] = ()

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
    operation_order: Tuple[int, ...]
    operation_ranks: Dict[int, int]
    resource_timelines: List[List[Any]]
    batch_end_times: Dict[str, datetime]
    changeovers_by_batch: Dict[str, float]
    latest_end_time: Optional[datetime]
    inherited_resources: Tuple[Tuple[int, str, str], ...]
    decoded_batch_order: Tuple[str, ...]
    pool_maps: Optional[Dict[str, Any]]


def prepare_repair_parent(
    candidate: Dict[str, Any], operations: List[Any], resource_pool: Optional[Dict[str, Any]],
    graph_context: Optional[Dict[str, Any]] = None, *, resource_moves: bool = False,
) -> RepairParentPreparation:
    """Prepare the decoded parent's static facts once; basis-specific signals remain separate."""
    by_id = _operations_by_id(operations)
    mutable = frozenset(by_id)
    mutable_batches = frozenset(str(op.batch_id) for op in operations)
    rows = _decoded_rows(candidate, by_id)
    current = {op_id: _fixed_resources(row) for op_id, row in rows.items()}
    inherited, pool_maps = _decoded_resource_facts(current, by_id, resource_pool, resource_moves=resource_moves)
    timelines_by_resource = resource_timeline_groups(candidate["results"])
    timelines = list(timelines_by_resource.values())
    batch_ends = {}
    for row in candidate["results"]:
        batch = str(row.batch_id)
        batch_ends[batch] = max(batch_ends.get(batch, row.end_time), row.end_time)
    changeovers = _batch_changeovers(timelines_by_resource, mutable_batches)
    predecessors, order = {}, ()
    if graph_context is not None and mutable and set(rows) == mutable:
        predecessors = {op_id: set(graph_context["predecessor_op_ids_by_op_id"].get(op_id, ())) & mutable
                        for op_id in mutable}
        order = decoded_topological_order(rows, predecessors)
    return RepairParentPreparation(
        operations_by_id=by_id, mutable_operation_ids=mutable, mutable_batch_ids=mutable_batches,
        decoded_rows=rows, current_resources=current, predecessors=predecessors, operation_order=order,
        operation_ranks={op_id: index for index, op_id in enumerate(order)}, resource_timelines=timelines,
        batch_end_times=batch_ends, changeovers_by_batch=changeovers,
        latest_end_time=max((row.end_time for row in rows.values()), default=None),
        inherited_resources=inherited, decoded_batch_order=tuple(decoded_batch_order(candidate["results"])),
        pool_maps=pool_maps,
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


def resource_timelines(results: List[Any]) -> List[List[Any]]:
    return list(resource_timeline_groups(results).values())


def resource_timeline_groups(results: List[Any]) -> Dict[Tuple[str, str], List[Any]]:
    timelines: Dict[Tuple[str, str], List[Any]] = defaultdict(list)
    for row in results:
        for field in ("machine_id", "operator_id"):
            resource = str(getattr(row, field, "") or "")
            if resource:
                timelines[(field, resource)].append(row)
    return {key: sorted(rows, key=lambda row: (row.start_time, row.end_time, int(row.op_id)))
            for key, rows in sorted(timelines.items())}


def _batch_changeovers(timelines: Dict[Tuple[str, str], List[Any]], batches: FrozenSet[str]) -> Dict[str, float]:
    counts: Dict[str, float] = {}
    for (kind, _resource), rows in timelines.items():
        if kind != "machine_id":
            continue
        previous = None
        previous_type = ""
        for row in rows:
            current_type = str(getattr(row, "op_type_name", "") or "").strip()
            if not current_type:
                continue
            if previous is not None and current_type != previous_type:
                for changed in (previous, row):
                    batch = str(changed.batch_id)
                    if batch in batches:
                        counts[batch] = counts.get(batch, 0.0) + 1.0
            previous, previous_type = row, current_type
    return counts


def apply_repair_decision(
    context: Dict[str, Any], operations: List[Any], decision: RepairDecision,
    resource_pool: Optional[Dict[str, Any]], *, share_unchanged: bool = False,
) -> Tuple[Dict[str, Any], List[Any]]:
    """Copy a decision into decoder inputs; precedence and fixed results stay intact."""
    if not isinstance(decision, RepairDecision):
        _invalid("decision")
    by_id = _operations_by_id(operations)
    out = repair_priority_context(context, operations=operations, order=list(decision.batch_order))
    if set(by_id).intersection(context.get("fixed_op_ids", ())):
        _invalid("fixed_op_ids", reason="graph_ready_repair_scope_mismatch")
    if decision.operation_order:
        if set(decision.operation_order) != set(by_id):
            _invalid("operation_order", reason="graph_ready_repair_scope_mismatch")
        batch_keys = out["graph_priority_key_by_op_id"]
        # This is ready-queue priority, not a forced topological execution order.
        out["graph_priority_key_by_op_id"] = {
            op_id: (float(rank),) + batch_keys[op_id]
            for rank, op_id in enumerate(decision.operation_order)
        }
    overrides = _validated_overrides(decision.resource_overrides, by_id, resource_pool)
    # Standalone/injected decoders retain independent input records. A certified native
    # decoder only reads them, so its unchanged records belong to the common run input.
    copied = [op if share_unchanged and op.id not in overrides else copy(op) for op in operations]
    for op in copied:
        if op.id in overrides:
            machine_id, operator_id = overrides[op.id]
            fixed_machine, fixed_operator = _fixed_resources(op)
            if not fixed_machine:
                op.machine_id = machine_id
            if not fixed_operator:
                op.operator_id = operator_id
    return out, copied


def native_readonly_inputs(schedule_fn: Any, scheduler: Any, operations: List[Any]) -> bool:
    from core.algorithms.greedy.scheduler import native_scheduler_inputs_unchanged
    from core.services.scheduler.run.optimizer.signature_support import schedule_with_optional_strict_mode

    return (
        schedule_fn is schedule_with_optional_strict_mode
        and native_scheduler_inputs_unchanged(scheduler)
        and type(operations) is list
        and _native_operation_classes(operations)
    )


def _native_operation_classes(operations):
    representatives = {type(op): op for op in operations}
    # Record methods are never called by SGS; certify each class once, including its accessors.
    return all(kind in _READONLY_OPERATION_GUARDS and _READONLY_OPERATION_GUARDS[kind](op)
               for kind, op in representatives.items())


def iter_resource_decisions(
    candidate: Dict[str, Any], operations: List[Any], resource_pool: Optional[Dict[str, Any]],
    batch_order: Tuple[str, ...], operation_order: Tuple[int, ...] = (), *, max_decisions: int = 8,
    prepared_parent: Optional[RepairParentPreparation] = None,
) -> Iterator[RepairDecision]:
    """Yield bounded one-operation moves, preserving previously accepted overrides."""
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int) or max_decisions <= 0:
        _invalid("max_decisions")
    if prepared_parent is None:
        by_id = _operations_by_id(operations)
        current = _current_resources(candidate, by_id)
        prior, prepared_pool = _decoded_resource_facts(current, by_id, resource_pool, resource_moves=True)
    else:
        by_id = prepared_parent.operations_by_id
        current = prepared_parent.current_resources
        prior, prepared_pool = prepared_parent.inherited_resources, prepared_parent.pool_maps
    base = RepairDecision(tuple(batch_order), tuple(operation_order), prior)
    repair_priority_context({}, operations=operations, order=list(base.batch_order))
    if base.operation_order and set(base.operation_order) != set(by_id):
        _invalid("operation_order", reason="graph_ready_repair_scope_mismatch")
    inherited = {op_id: (machine, operator) for op_id, machine, operator in prior}
    pool = prepared_pool if prepared_pool is not None else _pool_maps(resource_pool)
    generated = 0
    for op in operations:
        if not _can_change_resources(op):
            continue
        if op.id not in current:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
        if not all(current[op.id]):
            continue  # A point event without a selected pair does not introduce resources.
        for pair in _qualified_pairs(op, pool):
            if pair == current[op.id]:
                continue
            overrides = dict(inherited)
            overrides[op.id] = pair
            rows = tuple((op_id, values[0], values[1]) for op_id, values in sorted(overrides.items()))
            yield RepairDecision(base.batch_order, base.operation_order, rows)
            generated += 1
            if generated >= max_decisions:
                return


def _operations_by_id(operations: List[Any]) -> Dict[int, Any]:
    ids = [getattr(op, "id", None) for op in operations]
    _unique_ids(ids, field="operations")
    return dict(zip(cast(List[int], ids), operations))


def _unique_ids(values: Any, *, field: str) -> None:
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in values):
        _invalid(field)
    if len(values) != len(set(values)):
        _invalid(field)


def decoded_resource_overrides(
    candidate: Dict[str, Any], operations: List[Any], resource_pool: Optional[Dict[str, Any]],
    *, prepared_parent: Optional[RepairParentPreparation] = None,
) -> Tuple[Tuple[int, str, str], ...]:
    """Inherit actual mutable resource selections, independently of the parent's decision record."""
    if prepared_parent is not None:
        return prepared_parent.inherited_resources
    by_id = _operations_by_id(operations)
    current = _current_resources(candidate, by_id)
    return _decoded_resource_facts(current, by_id, resource_pool)[0]


def _decoded_resource_facts(
    current: Dict[int, Tuple[str, str]], by_id: Dict[int, Any], resource_pool: Optional[Dict[str, Any]],
    *, resource_moves: bool = False,
) -> Tuple[Tuple[Tuple[int, str, str], ...], Optional[Dict[str, Any]]]:
    rows = []
    for op_id, (machine, operator) in sorted(current.items()):
        op = by_id[op_id]
        fixed_machine, fixed_operator = _fixed_resources(op)
        if ((fixed_machine and machine and machine != fixed_machine)
                or (fixed_operator and operator and operator != fixed_operator)):
            _invalid("resource_overrides", reason="graph_ready_repair_fixed_resource")
        if _can_change_resources(op) and machine and operator:
            rows.append((op_id, machine, operator))
    overrides = tuple(rows)
    pool = _pool_maps(resource_pool) if overrides or resource_moves else None
    _validated_overrides(overrides, by_id, resource_pool, prepared_pool=pool)
    return overrides, pool


def _validated_overrides(
    rows: Tuple[Tuple[int, str, str], ...], by_id: Dict[int, Any], resource_pool: Optional[Dict[str, Any]],
    *, prepared_pool: Optional[Dict[str, Any]] = None,
) -> Dict[int, Tuple[str, str]]:
    if not rows:
        return {}
    pool = prepared_pool if prepared_pool is not None else _pool_maps(resource_pool)
    out = {}
    for op_id, machine_id, operator_id in rows:
        if op_id not in by_id:
            _invalid("resource_overrides", reason="graph_ready_repair_scope_mismatch")
        op = by_id[op_id]
        fixed_machine, fixed_operator = _fixed_resources(op)
        if (not _can_change_resources(op) or (fixed_machine and machine_id != fixed_machine)
                or (fixed_operator and operator_id != fixed_operator)):
            _invalid("resource_overrides", reason="graph_ready_repair_fixed_resource")
        if not _pair_is_qualified(op, machine_id, operator_id, pool):
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


def _resource_ids(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        _invalid("resource_pool")
    if any(not isinstance(v, str) or not v.strip() for v in value):
        _invalid("resource_pool")
    return tuple(sorted({v.strip() for v in value}))


def _fixed_resources(op: Any) -> Tuple[str, str]:
    return str(getattr(op, "machine_id", None) or "").strip(), str(getattr(op, "operator_id", None) or "").strip()


def _can_change_resources(op: Any) -> bool:
    machine, operator = _fixed_resources(op)
    return str(getattr(op, "source", "") or "").strip().lower() == "internal" and not (machine and operator)


def _qualified_pairs(op: Any, pool: Dict[str, Any]) -> Iterator[Tuple[str, str]]:
    fixed_machine, fixed_operator = _fixed_resources(op)
    op_type = str(getattr(op, "op_type_id", None) or "").strip()
    machines = (fixed_machine,) if fixed_machine else _resource_ids(pool["machines_by_op_type"].get(op_type, ()))
    for machine_id in machines:
        operators = _resource_ids(pool["operators_by_machine"].get(machine_id, ()))
        for operator_id in qualified_operators(pool, operators, op_type):
            if fixed_operator and operator_id != fixed_operator:
                continue
            if _pair_is_qualified(op, machine_id, operator_id, pool):
                yield machine_id, operator_id


def _pair_is_qualified(op: Any, machine_id: str, operator_id: str, pool: Dict[str, Any]) -> bool:
    fixed_machine, fixed_operator = _fixed_resources(op)
    op_type = str(getattr(op, "op_type_id", None) or "").strip()
    if not qualified_operators(pool, [operator_id], op_type):
        return False
    machines_by_type = pool["machines_by_op_type"]
    # The original fixed machine is an input constraint, as in auto_assign.py.
    # A newly selected machine always needs explicit operation-type evidence.
    if not fixed_machine or (op_type and op_type in machines_by_type):
        if not op_type or machine_id not in _resource_ids(machines_by_type.get(op_type, ())):
            return False
    if fixed_operator and not fixed_machine:
        operator_machines = _resource_ids(pool["machines_by_operator"].get(fixed_operator, ()))
        if operator_machines and machine_id not in operator_machines:
            return False
    return operator_id in _resource_ids(pool["operators_by_machine"].get(machine_id, ()))


def _current_resources(candidate: Dict[str, Any], by_id: Dict[int, Any]) -> Dict[int, Tuple[str, str]]:
    return {op_id: _fixed_resources(result) for op_id, result in _decoded_rows(candidate, by_id).items()}


def _decoded_rows(candidate: Dict[str, Any], by_id: Dict[int, Any]) -> Dict[int, Any]:
    out = {}
    for result in candidate["results"]:
        op_id = getattr(result, "op_id", None)
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
