from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, cast

from core.infrastructure.errors import ValidationError
from core.models.enums import SourceType

from .schedule_persistence_errors import raise_no_actionable_schedule_error

_ALLOWED_RESULT_SOURCES = frozenset((SourceType.INTERNAL.value, SourceType.EXTERNAL.value))


@dataclass(frozen=True)
class ValidatedScheduleRow:
    op_id: int
    machine_id: Any
    operator_id: Any
    start_time: datetime
    end_time: datetime
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


def _strict_positive_int(value: Any) -> int:
    if value is None or isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"invalid positive integer: {value!r}")
    number = int(value)
    if number <= 0:
        raise ValueError(f"invalid positive integer: {value!r}")
    return number


def _resource_text(value: Any) -> str:
    return str(value or "").strip()


def _source_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _iter_actionable_results(results: List[Any], *, allowed_op_ids: Optional[Set[int]] = None) -> Iterator[Tuple[int, Any]]:
    for result in results:
        if result is None or getattr(result, "op_id", None) is None:
            continue
        try:
            op_id = _strict_positive_int(getattr(result, "op_id", None))
        except (TypeError, ValueError):
            continue
        if allowed_op_ids is not None and op_id not in allowed_op_ids:
            continue

        start_time = getattr(result, "start_time", None)
        end_time = getattr(result, "end_time", None)
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
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


def _raise_invalid_schedule_rows_error(validation_errors: List[str]) -> None:
    exc = ValidationError("优化结果里有填写不对的排程记录，已拒绝写入。", field="schedule_results")
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
        except Exception as exc:
            parts.append(f"{field_name}=<unreadable:{type(exc).__name__}>")
            continue
        if value in (None, ""):
            continue
        parts.append(f"{field_name}={value}")
    return ",".join(parts)


def _operation_sources(operations: Optional[List[Any]]) -> Tuple[Dict[int, str], List[str]]:
    out: Dict[int, str] = {}
    errors: List[str] = []
    for index, op in enumerate(list(operations or [])):
        try:
            op_id = _strict_positive_int(getattr(op, "id", None))
        except (TypeError, ValueError):
            continue
        source = _source_text(getattr(op, "source", ""))
        if source not in _ALLOWED_RESULT_SOURCES:
            errors.append(f"operations[{index}],op_id={op_id}: source 必须是 internal 或 external")
            continue
        out[int(op_id)] = source
    return out, errors


def _resolve_schedule_row_source(
    result: Any,
    *,
    op_id: int,
    op_source_by_id: Dict[int, str],
    identity: str,
) -> Tuple[Optional[str], Optional[str]]:
    raw_source = _source_text(getattr(result, "source", ""))
    op_source = op_source_by_id.get(int(op_id))
    if raw_source and raw_source not in _ALLOWED_RESULT_SOURCES:
        return None, f"{identity}: source 必须是 internal 或 external"
    if op_source and raw_source and raw_source != op_source:
        return None, f"{identity}: source 与原工序不一致"
    source = op_source or raw_source
    if source not in _ALLOWED_RESULT_SOURCES:
        return None, f"{identity}: source 必须是 internal 或 external"
    return source, None


def _validate_schedule_row_resources(row: ValidatedScheduleRow, *, identity: str) -> Optional[str]:
    if row.source != SourceType.INTERNAL.value:
        return None
    if not _resource_text(row.machine_id) or not _resource_text(row.operator_id):
        return f"{identity}: internal 工序必须有设备和人员"
    return None


def _build_validated_schedule_row(
    result: Any,
    *,
    index: int,
    allowed_op_ids: Optional[Set[int]],
    op_source_by_id: Dict[int, str],
) -> Tuple[Optional[ValidatedScheduleRow], Optional[int], Optional[str]]:
    identity = _result_identity(result, index=index)
    if result is None:
        return None, None, f"{identity}: 排产结果为空"
    try:
        op_id = _strict_positive_int(getattr(result, "op_id", None))
    except (TypeError, ValueError):
        return None, None, f"{identity}: 工序编号不合法"
    if allowed_op_ids is not None and op_id not in allowed_op_ids:
        return None, int(op_id), None

    start_time = getattr(result, "start_time", None)
    end_time = getattr(result, "end_time", None)
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return None, None, f"{identity}: start_time/end_time 必须是有效时间"
    try:
        valid_time_range = start_time < end_time
    except Exception:
        return None, None, f"{identity}: start_time/end_time are not comparable"
    if not valid_time_range:
        return None, None, f"{identity}: start_time must be earlier than end_time"

    source, source_error = _resolve_schedule_row_source(
        result,
        op_id=int(op_id),
        op_source_by_id=op_source_by_id,
        identity=identity,
    )
    if source_error is not None:
        return None, None, source_error

    row = ValidatedScheduleRow(
        op_id=int(op_id),
        machine_id=getattr(result, "machine_id", None),
        operator_id=getattr(result, "operator_id", None),
        start_time=start_time,
        end_time=end_time,
        source=cast(str, source),
    )
    resource_error = _validate_schedule_row_resources(row, identity=identity)
    if resource_error is not None:
        return None, None, resource_error
    return row, None, None


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
    op_source_by_id, operation_source_errors = _operation_sources(operations)
    validation_errors.extend(operation_source_errors)

    for index, result in enumerate(list(results or [])):
        row, out_of_scope_op_id, validation_error = _build_validated_schedule_row(
            result,
            index=index,
            allowed_op_ids=allowed_op_ids,
            op_source_by_id=op_source_by_id,
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
        raise_no_actionable_schedule_error(
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


def _allowed_operation_ids(reschedulable_operations: List[Any]) -> Tuple[Set[int], Dict[int, str], List[str]]:
    op_source_by_id, operation_source_errors = _operation_sources(reschedulable_operations)
    allowed_op_ids = set(op_source_by_id.keys())
    for op in list(reschedulable_operations or []):
        try:
            allowed_op_ids.add(_strict_positive_int(getattr(op, "id", None)))
        except (TypeError, ValueError):
            continue
    return allowed_op_ids, op_source_by_id, list(operation_source_errors)


def _validate_payload_row(
    row: Any,
    *,
    index: int,
    allowed_op_ids: Set[int],
    op_source_by_id: Dict[int, str],
) -> Tuple[Optional[int], List[str]]:
    errors: List[str] = []
    identity = f"payload.schedule_rows[{index}],op_id={getattr(row, 'op_id', None)}"
    try:
        op_id = _strict_positive_int(getattr(row, "op_id", None))
    except (TypeError, ValueError):
        return None, [f"{identity}: 工序编号不合法"]
    if op_id not in allowed_op_ids:
        errors.append(f"{identity}: 工序超出本次可重排范围")
    start_time = getattr(row, "start_time", None)
    end_time = getattr(row, "end_time", None)
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        errors.append(f"{identity}: start_time/end_time 必须是有效时间")
        return int(op_id), errors
    if not start_time < end_time:
        errors.append(f"{identity}: start_time must be earlier than end_time")
    source = _source_text(getattr(row, "source", ""))
    if source not in _ALLOWED_RESULT_SOURCES:
        errors.append(f"{identity}: source 必须是 internal 或 external")
        return int(op_id), errors
    op_source = op_source_by_id.get(int(op_id))
    if op_source is None:
        errors.append(f"{identity}: 原工序 source 不可用")
        return int(op_id), errors
    if source != op_source:
        errors.append(f"{identity}: source 与原工序不一致")
        return int(op_id), errors
    resource_error = _validate_schedule_row_resources(
        ValidatedScheduleRow(
            op_id=int(op_id),
            machine_id=getattr(row, "machine_id", None),
            operator_id=getattr(row, "operator_id", None),
            start_time=start_time,
            end_time=end_time,
            source=source,
        ),
        identity=identity,
    )
    if resource_error is not None:
        errors.append(resource_error)
    return int(op_id), errors


def _duplicate_row_ids(row_ids: List[int]) -> List[int]:
    return sorted({op_id for op_id in row_ids if row_ids.count(op_id) > 1})


def _validate_scheduled_ids(raw_scheduled_op_ids: List[Any]) -> Tuple[Set[int], List[str]]:
    scheduled_ids: Set[int] = set()
    errors: List[str] = []
    for raw_op_id in raw_scheduled_op_ids:
        try:
            scheduled_id = _strict_positive_int(raw_op_id)
        except (TypeError, ValueError):
            errors.append(f"payload.scheduled_op_ids: 工序编号不合法 {raw_op_id!r}")
            continue
        if scheduled_id in scheduled_ids:
            errors.append(f"payload.scheduled_op_ids: 重复工序编号 {scheduled_id}")
        scheduled_ids.add(int(scheduled_id))
    return scheduled_ids, errors


def validate_payload_before_persist(
    payload: ValidatedSchedulePayload,
    *,
    reschedulable_operations: List[Any],
) -> None:
    row_ids: List[int] = []
    allowed_op_ids, op_source_by_id, validation_errors = _allowed_operation_ids(reschedulable_operations)
    for index, row in enumerate(list(payload.schedule_rows or [])):
        row_id, row_errors = _validate_payload_row(
            row,
            index=index,
            allowed_op_ids=allowed_op_ids,
            op_source_by_id=op_source_by_id,
        )
        validation_errors.extend(row_errors)
        if row_id is not None:
            row_ids.append(int(row_id))
    duplicates = _duplicate_row_ids(row_ids)
    if duplicates:
        validation_errors.append(f"payload.schedule_rows: 重复工序编号 {duplicates[:10]}")
    scheduled_ids, scheduled_id_errors = _validate_scheduled_ids(list(payload.scheduled_op_ids or []))
    validation_errors.extend(scheduled_id_errors)
    if set(row_ids) != scheduled_ids:
        validation_errors.append("payload.schedule_rows 与 scheduled_op_ids 不一致")
    if validation_errors:
        _raise_invalid_schedule_rows_error(validation_errors)


__all__ = [
    "ValidatedSchedulePayload",
    "ValidatedScheduleRow",
    "build_validated_schedule_payload",
    "count_actionable_schedule_rows",
    "has_actionable_schedule_rows",
    "validate_payload_before_persist",
]
