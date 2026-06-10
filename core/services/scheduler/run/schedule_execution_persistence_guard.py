from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import AppError, ErrorCode
from core.models.operation_execution_scope import OperationExecutionScope
from core.services.scheduler.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution_snapshot import build_execution_snapshot

from .schedule_input_contracts import _op_seq
from .schedule_payload_contract import ValidatedSchedulePayload, ValidatedScheduleRow


def _execution_guard_conflict(message: str, *, reason: str, op_id: Optional[int] = None) -> AppError:
    details: Dict[str, Any] = {"reason": reason}
    if op_id is not None:
        details["op_id"] = int(op_id)
    return AppError(ErrorCode.SCHEDULE_CONFLICT, message, details=details)


def _time_equal(left: Any, right: Any) -> bool:
    return isinstance(left, datetime) and isinstance(right, datetime) and left == right


def _resource_equal(left: Any, right: Any) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def _rows_by_op_id(payload: ValidatedSchedulePayload) -> Dict[int, ValidatedScheduleRow]:
    return {int(row.op_id): row for row in list(payload.schedule_rows or [])}


def _ops_by_id(operations: Optional[List[Any]]) -> Dict[int, Any]:
    out: Dict[int, Any] = {}
    for op in list(operations or []):
        try:
            op_id = int(getattr(op, "id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if op_id > 0:
            out[int(op_id)] = op
    return out


def _op_batch_id(op: Any) -> str:
    return str(getattr(op, "batch_id", "") or "").strip()


def _scope_from_fact(fact: ExecutionFact) -> Optional[OperationExecutionScope]:
    if not getattr(fact, "schedule_version", None) or not getattr(fact, "schedule_id", None):
        return None
    if not getattr(fact, "batch_id", None):
        return None
    return OperationExecutionScope.from_values(
        schedule_version=fact.schedule_version,
        schedule_id=fact.schedule_id,
        op_id=fact.op_id,
        batch_id=fact.batch_id,
        source_table=fact.source_table,
        effective_plan_role=fact.effective_plan_role,
        scenario_id=fact.scenario_id,
    )


def _scopes_from_facts(
    facts: Dict[int, ExecutionFact],
    op_ids: List[int],
) -> List[OperationExecutionScope]:
    scopes: List[OperationExecutionScope] = []
    missing: List[int] = []
    for op_id in op_ids:
        op_id_int = int(op_id)
        fact = facts.get(op_id_int)
        scope = _scope_from_fact(fact) if fact is not None else None
        if scope is None:
            missing.append(op_id_int)
            continue
        scopes.append(scope)
    if missing:
        raise _execution_guard_conflict(
            "现场状态快照缺少排程版本身份，本次没有写入新排程。请刷新后重新排。",
            reason="execution_scope_missing",
            op_id=missing[0],
        )
    return scopes


def _current_facts_for_expected(
    svc: Any,
    *,
    expected_op_ids: List[int],
    execution_facts: Dict[int, ExecutionFact],
) -> Dict[int, ExecutionFact]:
    scopes = _scopes_from_facts(execution_facts, expected_op_ids)
    return ExecutionFactProvider(svc.conn, logger=getattr(svc, "logger", None)).facts_by_op_id_for_scopes(
        scopes,
        include_op_ids=expected_op_ids,
    )


def _validate_execution_revisions(
    svc: Any,
    *,
    expected_revisions: Dict[int, str],
    execution_facts: Dict[int, ExecutionFact],
) -> None:
    if not expected_revisions:
        return
    expected_op_ids = sorted(int(op_id) for op_id in expected_revisions)
    current = _current_facts_for_expected(
        svc,
        expected_op_ids=expected_op_ids,
        execution_facts=execution_facts,
    )
    for op_id, expected_revision in expected_revisions.items():
        fact = current.get(int(op_id))
        current_revision = "" if fact is None else str(fact.state_revision or "")
        if current_revision != str(expected_revision or ""):
            raise _execution_guard_conflict(
                "现场状态刚刚变了，这次重排没有写入。请刷新后重新排。",
                reason="execution_state_changed",
                op_id=int(op_id),
            )


def _validate_execution_snapshot(
    svc: Any,
    *,
    expected_revision: Optional[str],
    expected_op_ids: Optional[List[int]],
    execution_facts: Dict[int, ExecutionFact],
) -> None:
    op_ids = [int(op_id) for op_id in list(expected_op_ids or []) if int(op_id) > 0]
    if not expected_revision or not op_ids:
        return
    current_facts = _current_facts_for_expected(
        svc,
        expected_op_ids=op_ids,
        execution_facts=execution_facts,
    )
    current = build_execution_snapshot(current_facts, op_ids)
    if current.revision != str(expected_revision or ""):
        raise _execution_guard_conflict(
            "现场状态刚刚变了，这次重排没有写入。请刷新后重新排。",
            reason="execution_state_changed",
        )


def _validate_processing_seed_row(
    *,
    row: ValidatedScheduleRow,
    fact: ExecutionFact,
) -> None:
    if not _time_equal(row.start_time, fact.actual_start_time):
        raise _execution_guard_conflict(
            "生产中的工序已经开工，重排不能改掉实际开工时间。本次没有写入新排程。请刷新后重新排。",
            reason="execution_fixed_start_moved",
            op_id=fact.op_id,
        )
    if not _resource_equal(row.machine_id, fact.actual_machine_id) or not _resource_equal(
        row.operator_id,
        fact.actual_operator_id,
    ):
        raise _execution_guard_conflict(
            "生产中的工序已经开工，重排不能改掉实际设备或人员。本次没有写入新排程。请刷新后重新排。",
            reason="execution_fixed_resource_moved",
            op_id=fact.op_id,
        )


def _validate_completed_seed_row(
    *,
    row: ValidatedScheduleRow,
    fact: ExecutionFact,
) -> None:
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


def _completed_downstream_rows(
    *,
    rows: Dict[int, ValidatedScheduleRow],
    operations: Optional[List[Any]],
    completed_op: Any,
    completed_op_id: int,
) -> List[Tuple[int, ValidatedScheduleRow]]:
    out = []
    completed_batch_id = _op_batch_id(completed_op)
    completed_seq = _op_seq(completed_op)
    if not completed_batch_id or completed_seq <= 0:
        return out
    for op_id, op in _ops_by_id(operations).items():
        if int(op_id) == int(completed_op_id):
            continue
        if _op_batch_id(op) != completed_batch_id or _op_seq(op) <= completed_seq:
            continue
        row = rows.get(int(op_id))
        if row is not None:
            out.append((int(op_id), row))
    return out


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

def _validate_completed_downstream_constraints(
    *,
    rows: Dict[int, ValidatedScheduleRow],
    operations: Optional[List[Any]],
    execution_facts: Dict[int, ExecutionFact],
    execution_completed_op_ids: Set[int],
) -> None:
    if not execution_completed_op_ids or not operations:
        return
    op_by_id = _ops_by_id(operations)
    for completed_op_id in sorted(set(execution_completed_op_ids or set())):
        completed_op = op_by_id.get(int(completed_op_id))
        fact = execution_facts.get(int(completed_op_id))
        if completed_op is None or fact is None or fact.actual_end_time is None:
            continue
        for op_id, row in _completed_downstream_rows(
            rows=rows,
            operations=operations,
            completed_op=completed_op,
            completed_op_id=int(completed_op_id),
        ):
            if row.start_time < fact.actual_end_time:
                _raise_completed_downstream_conflict(op_id=int(op_id), completed_op_id=int(completed_op_id))


def validate_execution_guard_before_persist(
    svc: Any,
    *,
    validated_schedule_payload: ValidatedSchedulePayload,
    execution_guard_state_revisions: Dict[int, str],
    execution_facts: Dict[int, ExecutionFact],
    execution_fixed_op_ids: Set[int],
    execution_completed_op_ids: Set[int],
    execution_snapshot_revision: Optional[str] = None,
    execution_snapshot_op_ids: Optional[List[int]] = None,
    payload_validation_operations: Optional[List[Any]] = None,
) -> None:
    if not execution_guard_state_revisions:
        return
    _validate_execution_snapshot(
        svc,
        expected_revision=execution_snapshot_revision,
        expected_op_ids=execution_snapshot_op_ids,
        execution_facts=execution_facts,
    )
    _validate_execution_revisions(
        svc,
        expected_revisions=execution_guard_state_revisions,
        execution_facts=execution_facts,
    )
    rows = _rows_by_op_id(validated_schedule_payload)
    for op_id in sorted(set(execution_fixed_op_ids or set())):
        fact = execution_facts.get(int(op_id))
        row = rows.get(int(op_id))
        if fact is None or row is None:
            raise _execution_guard_conflict(
                "生产中的工序必须保留在新排程里，本次没有写入新排程。请刷新后重新排。",
                reason="execution_fixed_row_missing",
                op_id=int(op_id),
            )
        _validate_processing_seed_row(row=row, fact=fact)
    for op_id in sorted(set(execution_completed_op_ids or set())):
        fact = execution_facts.get(int(op_id))
        row = rows.get(int(op_id))
        if fact is None or row is None:
            raise _execution_guard_conflict(
                "已完工的工序必须保留真实完工约束，本次没有写入新排程。请刷新后重新排。",
                reason="execution_completed_row_missing",
                op_id=int(op_id),
            )
        _validate_completed_seed_row(row=row, fact=fact)
    _validate_completed_downstream_constraints(
        rows=rows,
        operations=payload_validation_operations,
        execution_facts=execution_facts,
        execution_completed_op_ids=execution_completed_op_ids,
    )
