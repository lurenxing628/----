from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, cast

from core.infrastructure.errors import ValidationError
from core.models.enums import BatchOperationStatus, BatchStatus, SourceType, YesNo

_TERMINAL_OPERATION_STATUSES = frozenset((BatchOperationStatus.COMPLETED.value, BatchOperationStatus.SKIPPED.value))


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


def _missing_internal_resource_samples(
    operations: Optional[List[Any]],
    missing_internal_resource_op_ids: Optional[Set[int]],
) -> List[Dict[str, Any]]:
    missing_ids: Set[int] = set()
    for raw_op_id in set(missing_internal_resource_op_ids or set()):
        try:
            op_id = int(raw_op_id or 0)
        except Exception:
            continue
        if op_id > 0:
            missing_ids.add(op_id)
    if not missing_ids:
        return []
    samples: List[Dict[str, Any]] = []
    for op in sorted(
        list(operations or []),
        key=lambda item: (
            str(getattr(item, "batch_id", "") or ""),
            int(getattr(item, "seq", 0) or 0),
            int(getattr(item, "id", 0) or 0),
        ),
    ):
        op_id = int(getattr(op, "id", 0) or 0)
        if op_id not in missing_ids:
            continue
        missing_fields: List[str] = []
        if not str(getattr(op, "machine_id", "") or "").strip():
            missing_fields.append("设备")
        if not str(getattr(op, "operator_id", "") or "").strip():
            missing_fields.append("人员")
        samples.append(
            {
                "op_id": op_id,
                "batch_id": str(getattr(op, "batch_id", "") or ""),
                "op_code": str(getattr(op, "op_code", "") or ""),
                "seq": int(getattr(op, "seq", 0) or 0),
                "op_type_name": str(getattr(op, "op_type_name", "") or ""),
                "missing_fields": missing_fields,
            }
        )
    return samples


def _format_missing_internal_resource_sample(samples: List[Dict[str, Any]]) -> str:
    messages: List[str] = []
    for item in samples[:10]:
        label_parts = [
            str(item.get("batch_id") or "").strip(),
            f"工序{int(item.get('seq') or 0)}",
            str(item.get("op_type_name") or "").strip(),
        ]
        label = " / ".join([part for part in label_parts if part])
        missing_text = "、".join([str(field) for field in item.get("missing_fields") or []]) or "设备/人员"
        messages.append(f"{label} 缺{missing_text}")
    return "；".join(messages)


def _raise_no_actionable_schedule_error(
    validation_errors: Optional[List[str]] = None,
    *,
    operations: Optional[List[Any]] = None,
    missing_internal_resource_op_ids: Optional[Set[int]] = None,
) -> None:
    exc = ValidationError("优化结果未生成有效可落库排程行", field="schedule")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "no_actionable_schedule_rows"
    if validation_errors:
        exc.details["validation_errors"] = list(validation_errors)
    missing_samples = _missing_internal_resource_samples(operations, missing_internal_resource_op_ids)
    if missing_samples:
        total = len(missing_samples)
        sample_text = _format_missing_internal_resource_sample(missing_samples)
        suffix = f"；还有 {max(total - 10, 0)} 条未展示" if total > 10 else ""
        exc.details["missing_internal_resource_count"] = int(total)
        exc.details["missing_internal_resource_ops"] = missing_samples[:10]
        exc.details["user_message"] = (
            f"本次排产没有生成可保存结果，存在内部工序缺设备/人员："
            f"{sample_text}{suffix}。请先到批次工序补充页补齐后重试。"
        )
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


def _raise_duplicate_schedule_rows_error(duplicate_op_ids: List[int]) -> None:
    normalized_ids = sorted({int(op_id) for op_id in list(duplicate_op_ids or []) if int(op_id) > 0})
    exc = ValidationError("优化结果包含重复工序排程，已拒绝写入", field="schedule_results")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "duplicate_schedule_rows"
    exc.details["count"] = int(len(normalized_ids))
    exc.details["sample_op_ids"] = normalized_ids[:10]
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


def _build_validated_schedule_row(
    result: Any,
    *,
    index: int,
    allowed_op_ids: Optional[Set[int]],
) -> Tuple[Optional[ValidatedScheduleRow], Optional[int], Optional[str]]:
    identity = _result_identity(result, index=index)
    if result is None:
        return None, None, f"{identity}: result is None"
    try:
        op_id = int(getattr(result, "op_id", 0) or 0)
    except Exception:
        return None, None, f"{identity}: invalid op_id"
    if op_id <= 0:
        return None, None, f"{identity}: op_id must be positive"
    if allowed_op_ids is not None and op_id not in allowed_op_ids:
        return None, int(op_id), None

    start_time = getattr(result, "start_time", None)
    end_time = getattr(result, "end_time", None)
    if start_time is None or end_time is None:
        return None, None, f"{identity}: missing start_time/end_time"
    try:
        valid_time_range = start_time < end_time
    except Exception:
        return None, None, f"{identity}: start_time/end_time are not comparable"
    if not valid_time_range:
        return None, None, f"{identity}: start_time must be earlier than end_time"

    source = str(getattr(result, "source", "") or "").strip().lower()
    return (
        ValidatedScheduleRow(
            op_id=int(op_id),
            machine_id=getattr(result, "machine_id", None),
            operator_id=getattr(result, "operator_id", None),
            start_time=start_time,
            end_time=end_time,
            source=source,
        ),
        None,
        None,
    )


def build_validated_schedule_payload(
    results: List[Any],
    *,
    allowed_op_ids: Optional[Set[int]] = None,
    operations: Optional[List[Any]] = None,
    missing_internal_resource_op_ids: Optional[Set[int]] = None,
) -> ValidatedSchedulePayload:
    schedule_rows: List[ValidatedScheduleRow] = []
    scheduled_op_ids: Set[int] = set()
    assigned_by_op_id: Dict[int, Dict[str, Any]] = {}
    out_of_scope_op_ids: List[int] = []
    validation_errors: List[str] = []
    duplicate_op_ids: List[int] = []

    for index, result in enumerate(list(results or [])):
        row, out_of_scope_op_id, validation_error = _build_validated_schedule_row(
            result,
            index=index,
            allowed_op_ids=allowed_op_ids,
        )
        if out_of_scope_op_id is not None:
            out_of_scope_op_ids.append(int(out_of_scope_op_id))
            continue
        if validation_error is not None:
            validation_errors.append(validation_error)
            continue
        validated_row = cast(ValidatedScheduleRow, row)
        if int(validated_row.op_id) in scheduled_op_ids:
            duplicate_op_ids.append(int(validated_row.op_id))
            continue
        schedule_rows.append(validated_row)
        scheduled_op_ids.add(int(validated_row.op_id))
        if validated_row.source == SourceType.INTERNAL.value:
            assigned_by_op_id[int(validated_row.op_id)] = {
                "machine_id": validated_row.machine_id,
                "operator_id": validated_row.operator_id,
            }

    if out_of_scope_op_ids:
        _raise_out_of_scope_schedule_rows_error(out_of_scope_op_ids)
    if duplicate_op_ids:
        _raise_duplicate_schedule_rows_error(duplicate_op_ids)
    if validation_errors and schedule_rows:
        _raise_invalid_schedule_rows_error(validation_errors)
    if not schedule_rows:
        _raise_no_actionable_schedule_error(
            validation_errors,
            operations=operations,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )

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
        _raise_no_actionable_schedule_error(
            validated_schedule_payload.validation_errors,
            operations=reschedulable_operations,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        )

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
