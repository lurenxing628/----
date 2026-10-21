"""Capture requirements after the run has separated slots from retained seeds."""

from dataclasses import replace
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.errors import ValidationError
from core.models.enums import OperationQuantityBasis, OperationRequirementRole, OperationSetupState, SourceType
from core.models.operation_execution_event import EXECUTION_STATUS_COMPLETED

_SavedEffort = Union[OperationEffort, Mapping[str, Any]]


def _read(value: Any, field: str) -> Any:
    return value.get(field) if isinstance(value, Mapping) else getattr(value, field, None)


def _gap(field: str, code: str, message: str) -> Dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _role(op_id: int, slots: AbstractSet[int], seeds: Mapping[int, Any], fact: Any, projection: Any) -> str:
    completed = (_read(projection, "execution_state") == "complete"
                 or _read(fact, "actual_status") == EXECUTION_STATUS_COMPLETED)
    if completed:
        return OperationRequirementRole.COMPLETED.value
    if op_id in slots:
        return OperationRequirementRole.NEW_SCHEDULE.value
    if op_id in seeds:
        executing = (_read(seeds[op_id], "seed_source") == "execution_fact"
                     or _read(fact, "actual_start_time") is not None or _read(projection, "first_actual_start") is not None)
        return OperationRequirementRole.EXECUTION.value if executing else OperationRequirementRole.RETAINED.value
    return OperationRequirementRole.NOT_SCHEDULED.value


def _execution_quantities(fact: Any, projection: Any) -> Tuple[Any, Any, Any]:
    execution = projection if projection is not None else fact
    return (
        _read(execution, "target_quantity"),
        _read(execution, "remaining_quantity"),
        _read(execution, "target_basis" if projection is not None else "quantity_basis"),
    )


def _seed_effort(op: Any, role: str, saved: Optional[_SavedEffort], fact: Any, projection: Any) -> OperationEffort:
    execution_target, remaining, execution_basis = _execution_quantities(fact, projection)
    known = saved is not None and _read(saved, "required_standard_hours") is not None
    source: str = op.source
    state = (OperationSetupState.EXTERNAL.value if source == SourceType.EXTERNAL.value else
             OperationSetupState.ALREADY_COMPLETED.value if role == OperationRequirementRole.COMPLETED.value else
             OperationSetupState.RETAINED_IN_EXECUTION.value if role == OperationRequirementRole.EXECUTION.value and known else
             _read(saved, "setup_state") if known else OperationSetupState.UNKNOWN.value)
    gaps = tuple(_read(saved, "data_gaps") or ())
    if not known and source != SourceType.EXTERNAL.value:
        gap = (_gap("runtime_requirement", "runtime_requirement_not_constructed", "工序未进入本次排槽需求构造，实际标准需求未知。")
               if role == OperationRequirementRole.NOT_SCHEDULED.value else
               _gap("runtime_requirement", "runtime_requirement_missing", "原安排未保存实际标准需求分解，准备和加工工时未知。"))
        gaps += (gap,)
    cycle = _read(saved, "external_cycle_days")
    if source == SourceType.EXTERNAL.value and cycle is None:
        gap = (_gap("external_cycle_days", "external_cycle_not_constructed", "工序未进入本次外协排槽需求构造，实际外协周期未知。")
               if role == OperationRequirementRole.NOT_SCHEDULED.value else
               _gap("external_cycle_days", "external_cycle_missing", "原安排未保存外协周期依据。"))
        gaps += (gap,)
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=getattr(op, "piece_id", None), source=source,
        target_quantity=_read(saved, "target_quantity"), remaining_quantity=remaining,
        quantity_basis=_read(saved, "quantity_basis") or OperationQuantityBasis.UNKNOWN.value,
        execution_target_quantity=execution_target,
        execution_quantity_basis=execution_basis or OperationQuantityBasis.UNKNOWN.value,
        setup_standard_hours=_read(saved, "setup_standard_hours"),
        processing_standard_hours=_read(saved, "processing_standard_hours"),
        required_standard_hours=_read(saved, "required_standard_hours"), setup_state=state,
        requirement_role=role, external_cycle_days=cycle, external_group_id=_read(saved, "external_group_id"),
        external_merge_mode=_read(saved, "external_merge_mode"), data_gaps=gaps,
    )


def build_operation_efforts(
    *, operations: Sequence[Any], batches: Mapping[str, Any], algo_operations: Sequence[Any],
    operations_to_schedule: Sequence[Any], seed_results: Sequence[Mapping[str, Any]],
    execution_facts: Optional[Mapping[int, Any]] = None, execution_projections: Optional[Mapping[int, Any]] = None,
    saved_efforts: Optional[Mapping[int, _SavedEffort]] = None,
) -> List[OperationEffort]:
    """One item per input operation; saved seed decomposition stays immutable.

    ``saved_efforts`` must come from the authenticated source of that retained
    arrangement. The caller binds permanent operation references when saving.
    """
    algo = {op.id: op for op in algo_operations}
    slots = {op.id for op in operations_to_schedule}
    seeds = {row["op_id"]: row for row in seed_results}
    facts, projections, saved = execution_facts or {}, execution_projections or {}, saved_efforts or {}
    result = []
    for op in operations:
        fact, projection = facts.get(op.id), projections.get(op.id)
        role = _role(op.id, slots, seeds, fact, projection)
        if role != OperationRequirementRole.NEW_SCHEDULE.value:
            result.append(_seed_effort(op, role, saved.get(op.id), fact, projection))
            continue
        runtime_op = algo[op.id]
        batch = batches.get(runtime_op.batch_id)
        if batch is None:
            raise ValidationError("排槽工序缺少所属批次，实际标准需求无法计算。", field="batch_id")
        target, remaining, basis = _execution_quantities(fact, projection)
        if runtime_op.source == SourceType.INTERNAL.value:
            effort = internal_operation_effort(runtime_op, batch, remaining_quantity=remaining)
        elif runtime_op.source == SourceType.EXTERNAL.value:
            effort = external_operation_effort(runtime_op, batch, remaining_quantity=remaining)
        else:
            raise ValidationError("排槽工序的内制或外协来源不明确。", field="source")
        result.append(replace(effort, requirement_role=role, execution_target_quantity=target,
                              execution_quantity_basis=basis or OperationQuantityBasis.UNKNOWN.value))
    return result
