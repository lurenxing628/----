from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union, cast

from core.algorithm_contracts.schedule_point_evidence import verified_point
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.models.enums import SourceType
from core.shared.strict_parse import parse_required_int

from .schedule_persistence_errors import raise_no_actionable_schedule_error


@dataclass(frozen=True)
class ValidatedScheduleRow:
    op_id: int
    machine_id: Optional[str]
    operator_id: Optional[str]
    start_time: datetime
    end_time: datetime
    source: str


_ROW_FIELDS = tuple(item.name for item in fields(ValidatedScheduleRow))


def arrangement_row(values: Mapping[str, Any]) -> ValidatedScheduleRow:
    """一条种子或结果字典里的安排（工序、设备、人员、起止、来源），原值不校验，交给零工时见证和采用复核读取。"""
    return ValidatedScheduleRow(**{name: values[name] for name in _ROW_FIELDS})


# 写库前最终守卫接收的两种真实排程行：排产结果 ScheduleResult；候选采用按已存任务、试调采用按归档场景
# （trial_scenario_archive.schedule_rows）重建的 ValidatedScheduleRow。两者共有工序编号、设备、人员、起止和来源；
# 只有 ScheduleResult 另带工序代码、批次和工序号，供错误提示定位。
ScheduleRowInput = Union[ScheduleResult, ValidatedScheduleRow]
# 本次排产输入建好的零工时见证核对（workbench/facts/zero_duration.candidate_point_validator）。
PointValidator = Callable[[ValidatedScheduleRow], Any]


@dataclass(frozen=True)
class ValidatedSchedulePayload:
    schedule_rows: List[ValidatedScheduleRow]
    scheduled_op_ids: Set[int]
    assigned_by_op_id: Dict[int, Dict[str, Any]]
    out_of_scope_op_ids: List[int] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)


def _resource_text(value: Any) -> str:
    return str(value or "").strip()


def _source_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _raise_invalid_schedule_rows_error(validation_errors: List[str]) -> None:
    raise ValidationError(
        "优化结果里有填写不对的排程记录，已拒绝写入。",
        field="schedule_results",
        details={
            "reason": "invalid_schedule_rows",
            "validation_errors": list(validation_errors),
            "invalid_schedule_row_count": len(validation_errors),
        },
    )


def _raise_out_of_scope_schedule_rows_error(out_of_scope_op_ids: List[int]) -> None:
    normalized_ids = sorted(set(out_of_scope_op_ids))
    raise ValidationError(
        "优化结果包含超出本次可重排范围的工序，已拒绝写入",
        field="schedule_results",
        details={
            "reason": "out_of_scope_schedule_rows",
            "count": len(normalized_ids),
            "sample_op_ids": normalized_ids[:10],
            "allowed_scope_kind": "reschedulable_op_ids",
        },
    )


def _raise_duplicate_schedule_rows_error(duplicate_op_ids: List[int]) -> None:
    normalized_ids = sorted(set(duplicate_op_ids))
    raise ValidationError(
        "优化结果包含重复工序排程，已拒绝写入",
        field="schedule_results",
        details={
            "reason": "duplicate_schedule_rows",
            "count": len(normalized_ids),
            "sample_op_ids": normalized_ids[:10],
        },
    )


def _result_identity(result: Optional[ScheduleRowInput], *, index: int) -> str:
    if result is None:
        return f"results[{index}]"
    parts: List[str] = [f"index={index}"]
    named: List[Tuple[str, Any]] = [("op_id", result.op_id)]
    if isinstance(result, ScheduleResult):
        named += [("op_code", result.op_code), ("batch_id", result.batch_id), ("seq", result.seq)]
    for field_name, value in named:
        if value in (None, ""):
            continue
        parts.append(f"{field_name}={value}")
    return ",".join(parts)


def _resolve_schedule_row_source(
    result: ScheduleRowInput,
    *,
    op_id: int,
    op_source_by_id: Dict[int, str],
    identity: str,
) -> Tuple[Optional[str], Optional[str]]:
    raw_source = _source_text(result.source)
    op_source = op_source_by_id.get(op_id)
    if raw_source and raw_source not in OPERATION_SOURCES:
        return None, f"{identity}: source 必须是 internal 或 external"
    if op_source and raw_source and raw_source != op_source:
        return None, f"{identity}: source 与原工序不一致"
    source = op_source or raw_source
    if source not in OPERATION_SOURCES:
        return None, f"{identity}: source 必须是 internal 或 external"
    return source, None


def _validate_schedule_row_resources(row: ValidatedScheduleRow, *, identity: str) -> Optional[str]:
    if row.source != SourceType.INTERNAL.value:
        return None
    if not _resource_text(row.machine_id) or not _resource_text(row.operator_id):
        return f"{identity}: internal 工序必须有设备和人员"
    return None


def _build_validated_schedule_row(
    result: Optional[ScheduleRowInput],
    *,
    index: int,
    allowed_op_ids: Set[int],
    op_source_by_id: Dict[int, str],
    point_validator: PointValidator,
) -> Tuple[Optional[ValidatedScheduleRow], Optional[int], Optional[str]]:
    identity = _result_identity(result, index=index)
    if result is None:
        return None, None, f"{identity}: 排产结果为空"
    # 写库前最终守卫：结果行的工序编号在这里按共享严格口径解析一次。
    try:
        op_id = parse_required_int(result.op_id, field="op_id", min_value=1, reject_integer_float=True)
    except ValidationError:
        return None, None, f"{identity}: 工序编号不合法"
    if op_id not in allowed_op_ids:
        return None, op_id, None

    start_time = result.start_time
    end_time = result.end_time
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return None, None, f"{identity}: start_time/end_time 必须是有效时间"
    if start_time > end_time:
        return None, None, f"{identity}: start_time must be earlier than end_time"

    source, source_error = _resolve_schedule_row_source(
        result,
        op_id=op_id,
        op_source_by_id=op_source_by_id,
        identity=identity,
    )
    if source_error is not None:
        return None, None, source_error

    row = ValidatedScheduleRow(
        op_id=op_id,
        machine_id=result.machine_id,
        operator_id=result.operator_id,
        start_time=start_time,
        end_time=end_time,
        source=cast(str, source),
    )
    resource_error = _validate_schedule_row_resources(row, identity=identity)
    if resource_error is not None:
        return None, None, resource_error
    if start_time == end_time and not verified_point(row, point_validator):
        return None, None, f"{identity}: start_time must be earlier than end_time without verified point evidence"
    return row, None, None


def build_validated_schedule_payload(
    results: Sequence[Optional[ScheduleRowInput]],
    *,
    operations: List[BatchOperation],
    operation_sources: Dict[int, str],
    allowed_op_ids: Set[int],
    missing_internal_resource_op_ids: Set[int],
    schedule_errors: List[str],
    point_validator: PointValidator,
) -> ValidatedSchedulePayload:
    schedule_rows: List[ValidatedScheduleRow] = []
    scheduled_op_ids: Set[int] = set()
    assigned_by_op_id: Dict[int, Dict[str, Any]] = {}
    out_of_scope_op_ids: List[int] = []
    validation_errors: List[str] = []
    duplicate_op_ids: List[int] = []

    for index, result in enumerate(results):
        row, out_of_scope_op_id, validation_error = _build_validated_schedule_row(
            result,
            index=index,
            allowed_op_ids=allowed_op_ids,
            op_source_by_id=operation_sources,
            point_validator=point_validator,
        )
        if out_of_scope_op_id is not None:
            out_of_scope_op_ids.append(out_of_scope_op_id)
            continue
        if validation_error is not None:
            validation_errors.append(validation_error)
            continue
        validated_row = cast(ValidatedScheduleRow, row)
        op_id = validated_row.op_id
        if op_id in scheduled_op_ids:
            duplicate_op_ids.append(op_id)
            continue
        schedule_rows.append(validated_row)
        scheduled_op_ids.add(op_id)
        if validated_row.source == SourceType.INTERNAL.value:
            assigned_by_op_id[op_id] = {
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
            validation_errors + schedule_errors,
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


__all__ = [
    "ValidatedSchedulePayload",
    "ValidatedScheduleRow",
    "arrangement_row",
    "build_validated_schedule_payload",
]
