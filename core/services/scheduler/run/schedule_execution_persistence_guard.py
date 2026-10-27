from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from core.errors import AppError, ErrorCode
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable

from .schedule_input_runtime_support import validate_completed_downstream_intervals
from .schedule_input_seed_metadata import merged_external_group_identity, protected_interval_problem
from .schedule_payload_contract import ValidatedSchedulePayload, ValidatedScheduleRow


def _execution_guard_conflict(message: str, *, reason: str, op_id: int) -> AppError:
    return AppError(ErrorCode.SCHEDULE_CONFLICT, message, details={"reason": reason, "op_id": op_id})


def _time_equal(left: Any, right: Any) -> bool:
    return isinstance(left, datetime) and isinstance(right, datetime) and left == right


def _resource_equal(left: Any, right: Any) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def _rows_by_op_id(payload: ValidatedSchedulePayload) -> Dict[int, ValidatedScheduleRow]:
    return {row.op_id: row for row in payload.schedule_rows}


def _validate_completed_seed_row(
    *,
    row: ValidatedScheduleRow,
    fact: ExecutionFact,
) -> None:
    if fact.ledger_operation_ref is not None and (
        not _resource_equal(row.machine_id, fact.actual_machine_id)
        or not _resource_equal(row.operator_id, fact.actual_operator_id)
    ):
        raise _execution_guard_conflict(
            "已完工的报工工序不能改掉实际设备或人员，本次没有写入新排程。",
            reason="execution_completed_resource_moved",
            op_id=fact.op_id,
        )
    if fact.actual_start_time is not None and not _time_equal(row.start_time, fact.actual_start_time):
        raise _execution_guard_conflict(
            "已完工的工序不能被重排移动，本次没有写入新排程。请刷新后重新排。",
            reason="execution_completed_start_moved",
            op_id=fact.op_id,
        )
    if not _time_equal(row.end_time, fact.actual_end_time):
        raise _execution_guard_conflict(
            "已完工的工序不能被重排移动，本次没有写入新排程。请刷新后重新排。",
            reason="execution_completed_end_moved",
            op_id=fact.op_id,
        )


def _raise_completed_downstream_conflict(*, op_id: int, completed_op_id: int) -> None:
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "已完工的前道工序有真实完工时间，后续工序不能排在它之前。本次没有写入新排程。请刷新后重新排。",
        details={
            "reason": "execution_completed_downstream_before_actual_finish",
            "op_id": int(op_id),
            "completed_op_id": int(completed_op_id),
        },
    )


def _validate_completed_downstream_pair(completed_interval, row, *, completed_op_id, op_id, groups):
    problem = protected_interval_problem(
        completed_interval,
        {"start_time": row.start_time, "end_time": row.end_time},
        previous_group=groups.get(completed_op_id), current_group=groups.get(op_id))
    if problem == "merged_group_split":
        raise _execution_guard_conflict("同一个合并外协组的工序必须保持相同起止，本次没有写入新排程。",
            reason="execution_merged_group_split", op_id=op_id)
    if problem == "precedence_violation":
        _raise_completed_downstream_conflict(op_id=op_id, completed_op_id=completed_op_id)


def _validate_completed_downstream_constraints(*, rows, prepared):
    if not prepared.execution_completed_op_ids:
        return
    groups = {op.id: merged_external_group_identity(op) for op in prepared.algo_ops}
    completed_intervals = {
        completed_op_id: {
            "start_time": rows[completed_op_id].start_time,
            "end_time": prepared.execution_facts[completed_op_id].actual_end_time,
        }
        for completed_op_id in prepared.execution_completed_op_ids
    }
    validate_completed_downstream_intervals(
        operations_in_scope=((op.batch_id, op.seq, op.id) for op in prepared.operations if op.id in rows),
        groups=groups,
        completed_intervals=completed_intervals,
        validate_pair_fn=lambda completed_interval, op_id, *, completed_op_id: _validate_completed_downstream_pair(
            completed_interval, rows[op_id], completed_op_id=completed_op_id, op_id=op_id, groups=groups
        ),
    )


def validate_execution_guard_before_persist(prepared, *, validated_schedule_payload):
    """Validate a payload against facts prepared in this transaction's snapshot."""
    facts = prepared.execution_facts
    ensure_ledger_execution_schedulable(facts)
    rows = _rows_by_op_id(validated_schedule_payload)
    for op_id in sorted(prepared.execution_completed_op_ids):
        fact, row = facts.get(op_id), rows.get(op_id)
        if fact is None or row is None:
            raise _execution_guard_conflict(
                "已完工的工序必须保留真实完工约束，本次没有写入新排程。请刷新后重新排。",
                reason="execution_completed_row_missing", op_id=op_id)
        _validate_completed_seed_row(row=row, fact=fact)
    _validate_completed_downstream_constraints(rows=rows, prepared=prepared)
