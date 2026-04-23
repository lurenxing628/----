from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError
from core.models.enums import BatchOperationStatus, BatchStatus, SourceType, YesNo

_TERMINAL_OPERATION_STATUSES = frozenset(
    (BatchOperationStatus.COMPLETED.value, BatchOperationStatus.SKIPPED.value)
)


@dataclass(frozen=True)
class ValidatedScheduleRow:
    op_id: int
    machine_id: Any
    operator_id: Any
    start_time: Any
    end_time: Any
    source: str


@dataclass(frozen=True)
class ValidatedSchedulePayload:
    schedule_rows: List[ValidatedScheduleRow]
    scheduled_op_ids: Set[int]
    assigned_by_op_id: Dict[int, Dict[str, Any]]
    out_of_scope_op_ids: List[int] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)

    def to_repo_rows(self, svc: Any, *, version: int, frozen_op_ids: Set[int]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for row in self.schedule_rows:
            rows.append(
                {
                    "op_id": int(row.op_id),
                    "machine_id": row.machine_id,
                    "operator_id": row.operator_id,
                    "start_time": svc._format_dt(row.start_time),
                    "end_time": svc._format_dt(row.end_time),
                    "lock_status": "locked" if int(row.op_id) in frozen_op_ids else "unlocked",
                    "version": int(version),
                }
            )
        return rows


def _normalized_status_text(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower()
    return text or default


def _iter_actionable_results(
    results: List[Any],
    *,
    allowed_op_ids: Optional[Set[int]] = None,
) -> Iterator[Tuple[int, Any]]:
    for result in results:
        if result is None or getattr(result, "op_id", None) is None:
            continue
        try:
            op_id = int(getattr(result, "op_id", 0) or 0)
        except Exception:
            continue
        if op_id <= 0:
            continue
        if allowed_op_ids is not None and op_id not in allowed_op_ids:
            continue

        start_time = getattr(result, "start_time", None)
        end_time = getattr(result, "end_time", None)
        if not start_time or not end_time:
            continue
        try:
            if not (start_time < end_time):
                continue
        except Exception:
            continue
        yield op_id, result


def count_actionable_schedule_rows(results: List[Any], *, allowed_op_ids: Optional[Set[int]] = None) -> int:
    return sum(1 for _op_id, _result in _iter_actionable_results(results, allowed_op_ids=allowed_op_ids))


def has_actionable_schedule_rows(results: List[Any], *, allowed_op_ids: Optional[Set[int]] = None) -> bool:
    return count_actionable_schedule_rows(results, allowed_op_ids=allowed_op_ids) > 0


def _raise_no_actionable_schedule_error(validation_errors: Optional[List[str]] = None) -> None:
    exc = ValidationError("优化结果未生成有效可落库排程行", field="schedule")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "no_actionable_schedule_rows"
    if validation_errors:
        exc.details["validation_errors"] = list(validation_errors)
    raise exc


def _raise_invalid_schedule_rows_error(validation_errors: List[str]) -> None:
    exc = ValidationError("optimizer returned invalid in-scope schedule rows", field="schedule_results")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "invalid_schedule_rows"
    exc.details["validation_errors"] = list(validation_errors)
    exc.details["invalid_schedule_row_count"] = int(len(validation_errors))
    raise exc


def _raise_out_of_scope_schedule_rows_error(out_of_scope_op_ids: List[int]) -> None:
    normalized_ids = sorted({int(op_id) for op_id in list(out_of_scope_op_ids or []) if int(op_id) > 0})
    exc = ValidationError("优化结果包含超出本次可重排范围的工序，已拒绝写入", field="schedule_results")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "out_of_scope_schedule_rows"
    exc.details["count"] = int(len(normalized_ids))
    exc.details["sample_op_ids"] = normalized_ids[:10]
    exc.details["allowed_scope_kind"] = "reschedulable_op_ids"
    raise exc


def _result_identity(result: Any, *, index: int) -> str:
    if result is None:
        return f"results[{index}]"
    parts: List[str] = [f"index={index}"]
    for field_name in ("op_id", "op_code", "batch_id", "seq"):
        try:
            value = getattr(result, field_name, None)
        except Exception:
            value = None
        if value in (None, ""):
            continue
        parts.append(f"{field_name}={value}")
    return ",".join(parts)


def build_validated_schedule_payload(
    results: List[Any],
    *,
    allowed_op_ids: Optional[Set[int]] = None,
) -> ValidatedSchedulePayload:
    schedule_rows: List[ValidatedScheduleRow] = []
    scheduled_op_ids: Set[int] = set()
    assigned_by_op_id: Dict[int, Dict[str, Any]] = {}
    out_of_scope_op_ids: List[int] = []
    validation_errors: List[str] = []

    for index, result in enumerate(list(results or [])):
        identity = _result_identity(result, index=index)
        if result is None:
            validation_errors.append(f"{identity}: result is None")
            continue
        try:
            op_id = int(getattr(result, "op_id", 0) or 0)
        except Exception:
            validation_errors.append(f"{identity}: invalid op_id")
            continue
        if op_id <= 0:
            validation_errors.append(f"{identity}: op_id must be positive")
            continue
        if allowed_op_ids is not None and op_id not in allowed_op_ids:
            out_of_scope_op_ids.append(int(op_id))
            continue

        start_time = getattr(result, "start_time", None)
        end_time = getattr(result, "end_time", None)
        if start_time is None or end_time is None:
            validation_errors.append(f"{identity}: missing start_time/end_time")
            continue
        try:
            valid_time_range = start_time < end_time
        except Exception:
            validation_errors.append(f"{identity}: start_time/end_time are not comparable")
            continue
        if not valid_time_range:
            validation_errors.append(f"{identity}: start_time must be earlier than end_time")
            continue

        source = str(getattr(result, "source", "") or "").strip().lower()
        schedule_rows.append(
            ValidatedScheduleRow(
                op_id=int(op_id),
                machine_id=getattr(result, "machine_id", None),
                operator_id=getattr(result, "operator_id", None),
                start_time=start_time,
                end_time=end_time,
                source=source,
            )
        )
        scheduled_op_ids.add(int(op_id))
        if source == SourceType.INTERNAL.value:
            assigned_by_op_id[int(op_id)] = {
                "machine_id": getattr(result, "machine_id", None),
                "operator_id": getattr(result, "operator_id", None),
            }

    if out_of_scope_op_ids:
        _raise_out_of_scope_schedule_rows_error(out_of_scope_op_ids)
    if validation_errors and schedule_rows:
        _raise_invalid_schedule_rows_error(validation_errors)
    if not schedule_rows:
        _raise_no_actionable_schedule_error(validation_errors)

    return ValidatedSchedulePayload(
        schedule_rows=schedule_rows,
        scheduled_op_ids=scheduled_op_ids,
        assigned_by_op_id=assigned_by_op_id,
        out_of_scope_op_ids=out_of_scope_op_ids,
        validation_errors=validation_errors,
    )


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
) -> None:
    for op in reschedulable_operations:
        if not op.id:
            continue
        op_id = int(op.id)
        if op_id not in scheduled_op_ids:
            continue
        if _normalized_status_text(getattr(op, "status", None), default=BatchOperationStatus.PENDING.value) in _TERMINAL_OPERATION_STATUSES:
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
        "algo": result_summary_obj.get("algo"),
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
) -> None:
    if not validated_schedule_payload.schedule_rows:
        _raise_no_actionable_schedule_error(validated_schedule_payload.validation_errors)

    schedule_rows = validated_schedule_payload.to_repo_rows(
        svc,
        version=int(version),
        frozen_op_ids=frozen_op_ids,
    )

    with svc.tx_manager.transaction():
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
