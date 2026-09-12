from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_repair_neighbors import repair_priority_context


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


def apply_repair_decision(
    context: Dict[str, Any], operations: List[Any], decision: RepairDecision,
    resource_pool: Optional[Dict[str, Any]],
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
    copied = [copy(op) for op in operations]
    for op in copied:
        if op.id in overrides:
            machine_id, operator_id = overrides[op.id]
            fixed_machine, fixed_operator = _fixed_resources(op)
            if not fixed_machine:
                op.machine_id = machine_id
            if not fixed_operator:
                op.operator_id = operator_id
    return out, copied


def iter_resource_decisions(
    candidate: Dict[str, Any], operations: List[Any], resource_pool: Optional[Dict[str, Any]],
    batch_order: Tuple[str, ...], operation_order: Tuple[int, ...] = (), *, max_decisions: int = 8,
) -> Iterator[RepairDecision]:
    """Yield bounded one-operation moves, preserving previously accepted overrides."""
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int) or max_decisions <= 0:
        _invalid("max_decisions")
    by_id = _operations_by_id(operations)
    prior = _prior_overrides(candidate)
    base = RepairDecision(tuple(batch_order), tuple(operation_order), prior)
    repair_priority_context({}, operations=operations, order=list(base.batch_order))
    if base.operation_order and set(base.operation_order) != set(by_id):
        _invalid("operation_order", reason="graph_ready_repair_scope_mismatch")
    inherited = _validated_overrides(prior, by_id, resource_pool)
    pool = _pool_maps(resource_pool)
    current = _current_resources(candidate, by_id)
    generated = 0
    for op in operations:
        if not _can_change_resources(op):
            continue
        if op.id not in current:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
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


def _prior_overrides(candidate: Dict[str, Any]) -> Tuple[Tuple[int, str, str], ...]:
    prior = candidate.get("repair_decision")
    if prior is None:
        return ()
    if not isinstance(prior, dict):
        _invalid("repair_decision")
    rows = prior.get("resource_overrides", ())
    if not isinstance(rows, (list, tuple)) or any(not isinstance(row, (list, tuple)) for row in rows):
        _invalid("resource_overrides")
    result = tuple(tuple(row) for row in rows)
    RepairDecision((), resource_overrides=result)
    return result


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
        for operator_id in operators:
            if fixed_operator and operator_id != fixed_operator:
                continue
            if _pair_is_qualified(op, machine_id, operator_id, pool):
                yield machine_id, operator_id


def _pair_is_qualified(op: Any, machine_id: str, operator_id: str, pool: Dict[str, Any]) -> bool:
    fixed_machine, fixed_operator = _fixed_resources(op)
    op_type = str(getattr(op, "op_type_id", None) or "").strip()
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
    out = {}
    for result in candidate["results"]:
        op_id = getattr(result, "op_id", None)
        if op_id not in by_id:
            continue  # Fixed seed results are outside the mutable decision scope.
        if op_id in out:
            _invalid("results", reason="graph_ready_repair_scope_mismatch")
        out[op_id] = _fixed_resources(result)
    return out


def _invalid(field: str, *, reason: str = "graph_ready_repair_bad_decision") -> None:
    raise ValidationError(
        "GraphReady repair 决策无效：" + field, field="graph_ready_elite_repair", details={"reason": reason},
    )
