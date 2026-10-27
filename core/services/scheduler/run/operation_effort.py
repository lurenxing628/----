"""Capture requirements after the run has separated slots from retained seeds."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, AbstractSet, Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.enums import OperationQuantityBasis, OperationRequirementRole, OperationSetupState, SourceType
from core.models.operation_execution_scope import EXECUTION_STATUS_COMPLETED
from core.models.workbench_execution import ExecutionProjection

if TYPE_CHECKING:
    from core.services.scheduler.execution.execution_fact_provider import ExecutionFact


def _saved_field(saved: Optional[Mapping[str, Any]], field: str) -> Any:
    """An operation without a saved source, or with only a missing-source marker, has no saved value."""
    return None if saved is None else saved.get(field)


def _gap(field: str, code: str, message: str) -> Dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _role(op_id: int, slots: AbstractSet[int], seeds: Mapping[int, Mapping[str, Any]],
          fact: Optional[ExecutionFact], projection: ExecutionProjection) -> str:
    completed = (projection.execution_state == "complete"
                 or (fact is not None and fact.actual_status == EXECUTION_STATUS_COMPLETED))
    if completed:
        return OperationRequirementRole.COMPLETED.value
    if op_id in slots:
        return OperationRequirementRole.NEW_SCHEDULE.value
    if op_id in seeds:
        executing = (seeds[op_id].get("seed_source") == "execution_fact"
                     or (fact is not None and fact.actual_start_time is not None)
                     or projection.first_actual_start is not None)
        return OperationRequirementRole.EXECUTION.value if executing else OperationRequirementRole.RETAINED.value
    return OperationRequirementRole.NOT_SCHEDULED.value


def _execution_quantities(projection: ExecutionProjection) -> Tuple[Optional[int], Optional[int], str]:
    return projection.target_quantity, projection.remaining_quantity, projection.target_basis


def _seed_effort(op: BatchOperation, role: str, saved: Optional[Mapping[str, Any]],
                 projection: ExecutionProjection) -> OperationEffort:
    execution_target, remaining, execution_basis = _execution_quantities(projection)
    known = _saved_field(saved, "required_standard_hours") is not None
    source: str = op.source
    state = (OperationSetupState.EXTERNAL.value if source == SourceType.EXTERNAL.value else
             OperationSetupState.ALREADY_COMPLETED.value if role == OperationRequirementRole.COMPLETED.value else
             OperationSetupState.RETAINED_IN_EXECUTION.value if role == OperationRequirementRole.EXECUTION.value and known else
             _saved_field(saved, "setup_state") if known else OperationSetupState.UNKNOWN.value)
    gaps = tuple(_saved_field(saved, "data_gaps") or ())
    if not known and source != SourceType.EXTERNAL.value:
        gap = (_gap("runtime_requirement", "runtime_requirement_not_constructed", "工序未进入本次排槽需求构造，实际标准需求未知。")
               if role == OperationRequirementRole.NOT_SCHEDULED.value else
               _gap("runtime_requirement", "runtime_requirement_missing", "原安排未保存实际标准需求分解，准备和加工工时未知。"))
        gaps += (gap,)
    cycle = _saved_field(saved, "external_cycle_days")
    if source == SourceType.EXTERNAL.value and cycle is None:
        gap = (_gap("external_cycle_days", "external_cycle_not_constructed", "工序未进入本次外协排槽需求构造，实际外协周期未知。")
               if role == OperationRequirementRole.NOT_SCHEDULED.value else
               _gap("external_cycle_days", "external_cycle_missing", "原安排未保存外协周期依据。"))
        gaps += (gap,)
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=op.piece_id, source=source,
        target_quantity=_saved_field(saved, "target_quantity"), remaining_quantity=remaining,
        quantity_basis=_saved_field(saved, "quantity_basis") or OperationQuantityBasis.UNKNOWN.value,
        execution_target_quantity=execution_target,
        execution_quantity_basis=execution_basis or OperationQuantityBasis.UNKNOWN.value,
        setup_standard_hours=_saved_field(saved, "setup_standard_hours"),
        processing_standard_hours=_saved_field(saved, "processing_standard_hours"),
        required_standard_hours=_saved_field(saved, "required_standard_hours"), setup_state=state,
        requirement_role=role, external_cycle_days=cycle, external_group_id=_saved_field(saved, "external_group_id"),
        external_merge_mode=_saved_field(saved, "external_merge_mode"), data_gaps=gaps,
    )


def build_operation_efforts(
    *, operations: Sequence[BatchOperation], batches: Mapping[str, Batch], algo_operations: Sequence[OpForScheduleAlgo],
    operations_to_schedule: Sequence[OpForScheduleAlgo], seed_results: Sequence[Mapping[str, Any]],
    execution_facts: Mapping[int, ExecutionFact], execution_projections: Mapping[int, ExecutionProjection],
    saved_efforts: Mapping[int, Mapping[str, Any]],
) -> List[OperationEffort]:
    """One item per input operation; saved seed decomposition stays immutable.

    ``saved_efforts`` must come from the authenticated source of that retained
    arrangement. The caller binds permanent operation references when saving.
    """
    algo = {op.id: op for op in algo_operations}
    slots = {op.id for op in operations_to_schedule}
    seeds = {row["op_id"]: row for row in seed_results}
    result = []
    for op in operations:
        projection = execution_projections[op.id]
        role = _role(op.id, slots, seeds, execution_facts.get(op.id), projection)
        if role != OperationRequirementRole.NEW_SCHEDULE.value:
            result.append(_seed_effort(op, role, saved_efforts.get(op.id), projection))
            continue
        # 排槽工序来自本次输入构建：所属批次必在本次批次里，来源只会是自制或外协。
        runtime_op = algo[op.id]
        batch = batches[runtime_op.batch_id]
        target, remaining, basis = _execution_quantities(projection)
        if runtime_op.source == SourceType.INTERNAL.value:
            effort = internal_operation_effort(runtime_op, batch, remaining_quantity=remaining)
        else:
            effort = external_operation_effort(runtime_op, batch, remaining_quantity=remaining)
        result.append(replace(effort, requirement_role=role, execution_target_quantity=target,
                              execution_quantity_basis=basis or OperationQuantityBasis.UNKNOWN.value))
    return result
