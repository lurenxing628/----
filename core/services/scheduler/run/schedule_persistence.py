from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import BatchOperationStatus, BatchStatus, YesNo
from core.services.scheduler.execution_fact_provider import ExecutionFact

from .schedule_candidate_persistence_helpers import persist_schedule_run_with_candidates as _persist_with_candidates
from .schedule_candidate_persistence_models import operation_log_algo_summary as _operation_log_algo_summary
from .schedule_execution_persistence_guard import validate_execution_guard_before_persist
from .schedule_payload_contract import (
    ValidatedSchedulePayload,
    ValidatedScheduleRow,
    build_validated_schedule_payload,
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


def _guarded_frozen_op_ids(
    frozen_op_ids: Set[int],
    execution_fixed_op_ids: Optional[Set[int]],
    execution_completed_op_ids: Optional[Set[int]],
) -> Set[int]:
    return set(frozen_op_ids or set()) | set(execution_fixed_op_ids or set()) | set(execution_completed_op_ids or set())


def _validate_persist_inputs(
    svc,
    *,
    validated_schedule_payload: ValidatedSchedulePayload,
    reschedulable_operations: List[Any],
    missing_internal_resource_op_ids: Set[int],
    execution_fixed_op_ids: Optional[Set[int]],
    execution_completed_op_ids: Optional[Set[int]],
    execution_guard_state_revisions: Optional[Dict[int, str]],
    execution_snapshot_revision: Optional[str],
    execution_snapshot_op_ids: Optional[List[int]],
    execution_facts: Optional[Dict[int, ExecutionFact]],
    payload_validation_operations: Optional[List[Any]],
) -> None:
    if not validated_schedule_payload.schedule_rows:
        raise_no_actionable_schedule_error(
            validated_schedule_payload.validation_errors,
            operations=reschedulable_operations,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )
    validation_operations = payload_validation_operations or reschedulable_operations
    _validate_payload_before_persist(validated_schedule_payload, reschedulable_operations=validation_operations)
    validate_execution_guard_before_persist(
        svc,
        validated_schedule_payload=validated_schedule_payload,
        execution_guard_state_revisions=dict(execution_guard_state_revisions or {}),
        execution_facts=dict(execution_facts or {}),
        execution_fixed_op_ids=set(execution_fixed_op_ids or set()),
        execution_completed_op_ids=set(execution_completed_op_ids or set()),
        execution_snapshot_revision=execution_snapshot_revision,
        execution_snapshot_op_ids=list(execution_snapshot_op_ids or []),
        payload_validation_operations=validation_operations,
    )


def _persist_non_simulation_state(
    svc,
    *,
    cfg: Any,
    validated_schedule_payload: ValidatedSchedulePayload,
    batches: Dict[str, Any],
    reschedulable_operations: List[Any],
    missing_internal_resource_op_ids: Set[int],
    execution_fixed_op_ids: Optional[Set[int]],
    execution_completed_op_ids: Optional[Set[int]],
) -> None:
    auto_assign_persist = str(cfg.auto_assign_persist or "").strip().lower() == YesNo.YES.value
    _persist_operation_statuses(
        svc,
        reschedulable_operations=reschedulable_operations,
        scheduled_op_ids=set(validated_schedule_payload.scheduled_op_ids),
        auto_assign_persist=auto_assign_persist,
        missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        assigned_by_op_id=dict(validated_schedule_payload.assigned_by_op_id),
        execution_status_protected_op_ids=set(execution_fixed_op_ids or set()) | set(execution_completed_op_ids or set()),
    )
    _persist_batch_statuses(
        svc,
        batches=batches,
        reschedulable_operations=reschedulable_operations,
        scheduled_op_ids=set(validated_schedule_payload.scheduled_op_ids),
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
    _validate_persist_inputs(
        svc,
        validated_schedule_payload=validated_schedule_payload,
        reschedulable_operations=reschedulable_operations,
        missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        execution_fixed_op_ids=execution_fixed_op_ids,
        execution_completed_op_ids=execution_completed_op_ids,
        execution_guard_state_revisions=execution_guard_state_revisions,
        execution_snapshot_revision=execution_snapshot_revision,
        execution_snapshot_op_ids=execution_snapshot_op_ids,
        execution_facts=execution_facts,
        payload_validation_operations=payload_validation_operations,
    )

    schedule_rows = validated_schedule_payload.to_repo_rows(
        svc,
        version=int(version),
        frozen_op_ids=_guarded_frozen_op_ids(frozen_op_ids, execution_fixed_op_ids, execution_completed_op_ids),
    )

    if schedule_rows:
        svc.schedule_repo.bulk_create(schedule_rows)

    if not simulate:
        _persist_non_simulation_state(
            svc,
            cfg=cfg,
            validated_schedule_payload=validated_schedule_payload,
            batches=batches,
            reschedulable_operations=reschedulable_operations,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
            execution_fixed_op_ids=execution_fixed_op_ids,
            execution_completed_op_ids=execution_completed_op_ids,
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
