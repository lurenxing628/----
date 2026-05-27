from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import AppError, ErrorCode
from core.models.enums import BatchOperationStatus, BatchStatus, YesNo
from core.services.scheduler.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution_snapshot import collect_execution_snapshot

from .schedule_candidate_persistence_helpers import persist_schedule_run_with_candidates as _persist_with_candidates
from .schedule_candidate_persistence_models import operation_log_algo_summary as _operation_log_algo_summary
from .schedule_payload_contract import (
    ValidatedSchedulePayload,
    ValidatedScheduleRow,
    build_validated_schedule_payload,
    count_actionable_schedule_rows,
    has_actionable_schedule_rows,
)
from .schedule_payload_contract import (
    validate_payload_before_persist as _validate_payload_before_persist,
)
from .schedule_persistence_errors import raise_no_actionable_schedule_error

_TERMINAL_OPERATION_STATUSES = frozenset((BatchOperationStatus.COMPLETED.value, BatchOperationStatus.SKIPPED.value))


def _normalized_status_text(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower()
    return text or default


def _maybe_persist_auto_assign_resources(
    svc,
    *,
    op: Any,
    op_id: int,
    auto_assign_persist: bool,
    missing_internal_resource_op_ids: Set[int],
    assigned_by_op_id: Dict[int, Dict[str, Any]],
) -> None:
    if (not auto_assign_persist) or (op_id not in missing_internal_resource_op_ids):
        return
    assign = assigned_by_op_id.get(op_id) or {}
    mc = (assign.get("machine_id") or "").strip()
    oid = (assign.get("operator_id") or "").strip()
    updates: Dict[str, Any] = {}
    if mc and not (str(getattr(op, "machine_id", "") or "").strip()):
        updates["machine_id"] = mc
    if oid and not (str(getattr(op, "operator_id", "") or "").strip()):
        updates["operator_id"] = oid
    if updates:
        svc.op_repo.update(op_id, updates)


def _persist_operation_statuses(
    svc,
    *,
    reschedulable_operations: List[Any],
    scheduled_op_ids: Set[int],
    auto_assign_persist: bool,
    missing_internal_resource_op_ids: Set[int],
    assigned_by_op_id: Dict[int, Dict[str, Any]],
    execution_status_protected_op_ids: Set[int],
) -> None:
    for op in reschedulable_operations:
        if not op.id:
            continue
        op_id = int(op.id)
        if op_id not in scheduled_op_ids:
            continue
        if op_id in execution_status_protected_op_ids:
            continue
        if (
            _normalized_status_text(getattr(op, "status", None), default=BatchOperationStatus.PENDING.value)
            in _TERMINAL_OPERATION_STATUSES
        ):
            continue
        svc.op_repo.update(op_id, {"status": BatchOperationStatus.SCHEDULED.value})
        _maybe_persist_auto_assign_resources(
            svc,
            op=op,
            op_id=op_id,
            auto_assign_persist=auto_assign_persist,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
            assigned_by_op_id=assigned_by_op_id,
        )


def _persist_batch_statuses(
    svc,
    *,
    batches: Dict[str, Any],
    reschedulable_operations: List[Any],
    scheduled_op_ids: Set[int],
) -> None:
    by_batch_total: Dict[str, int] = {}
    by_batch_scheduled: Dict[str, int] = {}
    for op in reschedulable_operations:
        by_batch_total[op.batch_id] = by_batch_total.get(op.batch_id, 0) + 1
        if op.id and int(op.id) in scheduled_op_ids:
            by_batch_scheduled[op.batch_id] = by_batch_scheduled.get(op.batch_id, 0) + 1

    for bid, batch in batches.items():
        total = by_batch_total.get(bid, 0)
        if total <= 0:
            continue
        ok = by_batch_scheduled.get(bid, 0)
        new_status = BatchStatus.SCHEDULED.value if total > 0 and ok == total else BatchStatus.PENDING.value
        current_status = _normalized_status_text(getattr(batch, "status", None), default=BatchStatus.PENDING.value)
        if new_status != current_status:
            svc.batch_repo.update(bid, {"status": new_status})


def _persist_schedule_history(
    svc,
    *,
    version: int,
    used_strategy: Any,
    batches: Dict[str, Any],
    summary: Any,
    result_status: str,
    result_summary_json: str,
    created_by: str,
) -> None:
    svc.history_repo.create(
        {
            "version": int(version),
            "strategy": used_strategy.value,
            "batch_count": len(batches),
            "op_count": int(getattr(summary, "total_ops", 0)),
            "result_status": result_status,
            "result_summary": result_summary_json,
            "created_by": str(created_by or "system"),
        }
    )


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


def _op_seq(op: Any) -> int:
    try:
        return int(getattr(op, "seq", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _validate_execution_revisions(
    svc: Any,
    *,
    expected_revisions: Dict[int, str],
) -> None:
    if not expected_revisions:
        return
    current = ExecutionFactProvider(svc.conn, logger=getattr(svc, "logger", None)).facts_by_op_id(
        sorted(expected_revisions)
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
) -> None:
    op_ids = [int(op_id) for op_id in list(expected_op_ids or []) if int(op_id) > 0]
    if not expected_revision or not op_ids:
        return
    current = collect_execution_snapshot(svc.conn, op_ids, logger=getattr(svc, "logger", None))
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
        completed_batch_id = _op_batch_id(completed_op)
        completed_seq = _op_seq(completed_op)
        if not completed_batch_id or completed_seq <= 0:
            continue
        for op_id, op in op_by_id.items():
            if int(op_id) == int(completed_op_id):
                continue
            if _op_batch_id(op) != completed_batch_id or _op_seq(op) <= completed_seq:
                continue
            row = rows.get(int(op_id))
            if row is not None and row.start_time < fact.actual_end_time:
                raise AppError(
                    ErrorCode.SCHEDULE_CONFLICT,
                    "已完工的前道工序有真实完工时间，后续工序不能排在它之前。本次没有写入新排程。请刷新后重新排。",
                    details={
                        "reason": "execution_completed_downstream_before_actual_finish",
                        "op_id": int(op_id),
                        "completed_op_id": int(completed_op_id),
                    },
                )


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
    )
    _validate_execution_revisions(svc, expected_revisions=execution_guard_state_revisions)
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


def _log_schedule_operation(
    svc,
    *,
    version: int,
    simulate: bool,
    used_strategy: Any,
    used_params: Dict[str, Any],
    result_summary_obj: Dict[str, Any],
    normalized_batch_ids: List[str],
    batches: Dict[str, Any],
    summary: Any,
    result_status: str,
    overdue_items: List[Dict[str, Any]],
    time_cost_ms: int,
) -> None:
    if svc.op_logger is None:
        return
    detail = {
        "is_simulation": bool(simulate),
        "version": int(version),
        "strategy": used_strategy.value,
        "strategy_params": used_params or {},
        "algo": _operation_log_algo_summary(result_summary_obj),
        "batch_ids": list(normalized_batch_ids),
        "batch_count": len(batches),
        "op_count": int(getattr(summary, "total_ops", 0)),
        "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
        "failed_ops": int(getattr(summary, "failed_ops", 0)),
        "result_status": result_status,
        "overdue_count": len(overdue_items),
        "overdue_batches_sample": overdue_items[:10],
        "time_cost_ms": int(time_cost_ms),
    }
    svc.op_logger.info(
        module="scheduler",
        action="simulate" if simulate else "schedule",
        target_type="schedule",
        target_id=str(version),
        detail=detail,
    )


def persist_schedule_core_in_tx(
    svc,
    *,
    cfg: Any,
    version: int,
    validated_schedule_payload: ValidatedSchedulePayload,
    summary: Any,
    used_strategy: Any,
    batches: Dict[str, Any],
    reschedulable_operations: List[Any],
    created_by: str,
    simulate: bool,
    frozen_op_ids: Set[int],
    result_status: str,
    result_summary_json: str,
    missing_internal_resource_op_ids: Set[int],
    execution_fixed_op_ids: Optional[Set[int]] = None,
    execution_completed_op_ids: Optional[Set[int]] = None,
    execution_guard_state_revisions: Optional[Dict[int, str]] = None,
    execution_snapshot_revision: Optional[str] = None,
    execution_snapshot_op_ids: Optional[List[int]] = None,
    execution_facts: Optional[Dict[int, ExecutionFact]] = None,
    payload_validation_operations: Optional[List[Any]] = None,
) -> None:
    if not validated_schedule_payload.schedule_rows:
        raise_no_actionable_schedule_error(
            validated_schedule_payload.validation_errors,
            operations=reschedulable_operations,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )
    _validate_payload_before_persist(
        validated_schedule_payload,
        reschedulable_operations=payload_validation_operations
        if payload_validation_operations is not None
        else reschedulable_operations,
    )
    validate_execution_guard_before_persist(
        svc,
        validated_schedule_payload=validated_schedule_payload,
        execution_guard_state_revisions=dict(execution_guard_state_revisions or {}),
        execution_facts=dict(execution_facts or {}),
        execution_fixed_op_ids=set(execution_fixed_op_ids or set()),
        execution_completed_op_ids=set(execution_completed_op_ids or set()),
        execution_snapshot_revision=execution_snapshot_revision,
        execution_snapshot_op_ids=list(execution_snapshot_op_ids or []),
        payload_validation_operations=payload_validation_operations
        if payload_validation_operations is not None
        else reschedulable_operations,
    )

    schedule_rows = validated_schedule_payload.to_repo_rows(
        svc,
        version=int(version),
        frozen_op_ids=set(frozen_op_ids or set())
        | set(execution_fixed_op_ids or set())
        | set(execution_completed_op_ids or set()),
    )

    if schedule_rows:
        svc.schedule_repo.bulk_create(schedule_rows)

    if not simulate:
        auto_assign_persist = str(cfg.auto_assign_persist or "").strip().lower() == YesNo.YES.value
        scheduled_op_ids = set(validated_schedule_payload.scheduled_op_ids)
        assigned_by_op_id = dict(validated_schedule_payload.assigned_by_op_id)

        _persist_operation_statuses(
            svc,
            reschedulable_operations=reschedulable_operations,
            scheduled_op_ids=scheduled_op_ids,
            auto_assign_persist=auto_assign_persist,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
            assigned_by_op_id=assigned_by_op_id,
            execution_status_protected_op_ids=set(execution_fixed_op_ids or set())
            | set(execution_completed_op_ids or set()),
        )

        _persist_batch_statuses(
            svc,
            batches=batches,
            reschedulable_operations=reschedulable_operations,
            scheduled_op_ids=scheduled_op_ids,
        )

    _persist_schedule_history(
        svc,
        version=int(version),
        used_strategy=used_strategy,
        batches=batches,
        summary=summary,
        result_status=result_status,
        result_summary_json=result_summary_json,
        created_by=created_by,
    )


def persist_schedule(
    svc,
    *,
    cfg: Any,
    version: int,
    validated_schedule_payload: ValidatedSchedulePayload,
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    batches: Dict[str, Any],
    reschedulable_operations: List[Any],
    normalized_batch_ids: List[str],
    created_by: str,
    simulate: bool,
    frozen_op_ids: Set[int],
    result_status: str,
    result_summary_json: str,
    result_summary_obj: Dict[str, Any],
    missing_internal_resource_op_ids: Set[int],
    overdue_items: List[Dict[str, Any]],
    time_cost_ms: int,
    execution_fixed_op_ids: Optional[Set[int]] = None,
    execution_completed_op_ids: Optional[Set[int]] = None,
    execution_guard_state_revisions: Optional[Dict[int, str]] = None,
    execution_snapshot_revision: Optional[str] = None,
    execution_snapshot_op_ids: Optional[List[int]] = None,
    execution_facts: Optional[Dict[int, ExecutionFact]] = None,
    payload_validation_operations: Optional[List[Any]] = None,
) -> None:
    with svc.tx_manager.transaction():
        persist_schedule_core_in_tx(
            svc,
            cfg=cfg,
            version=version,
            validated_schedule_payload=validated_schedule_payload,
            summary=summary,
            used_strategy=used_strategy,
            batches=batches,
            reschedulable_operations=reschedulable_operations,
            created_by=created_by,
            simulate=simulate,
            frozen_op_ids=frozen_op_ids,
            execution_fixed_op_ids=set(execution_fixed_op_ids or set()),
            execution_completed_op_ids=set(execution_completed_op_ids or set()),
            execution_guard_state_revisions=dict(execution_guard_state_revisions or {}),
            execution_snapshot_revision=execution_snapshot_revision,
            execution_snapshot_op_ids=list(execution_snapshot_op_ids or []),
            execution_facts=dict(execution_facts or {}),
            payload_validation_operations=payload_validation_operations,
            result_status=result_status,
            result_summary_json=result_summary_json,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )

    _log_schedule_operation(
        svc,
        version=int(version),
        simulate=simulate,
        used_strategy=used_strategy,
        used_params=used_params,
        result_summary_obj=result_summary_obj,
        normalized_batch_ids=normalized_batch_ids,
        batches=batches,
        summary=summary,
        result_status=result_status,
        overdue_items=overdue_items,
        time_cost_ms=time_cost_ms,
    )


def persist_schedule_run_with_candidates(svc: Any, **kwargs: Any) -> None:
    _persist_with_candidates(svc, persist_schedule_core_in_tx=persist_schedule_core_in_tx, log_schedule_operation=_log_schedule_operation, **kwargs)
