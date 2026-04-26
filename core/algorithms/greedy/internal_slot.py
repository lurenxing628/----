from __future__ import annotations

import inspect
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError

from .downtime import find_overlap_shift_end

_MISSING = object()


@dataclass(frozen=True)
class InternalSlotEstimate:
    machine_id: str
    operator_id: str
    start_time: datetime
    end_time: datetime
    total_hours: float
    changeover_penalty: int
    blocked_by_window: bool = False
    abort_after_hit: bool = False
    efficiency_fallback_used: bool = False


@dataclass(frozen=True)
class _SlotAttempt:
    start_time: datetime
    end_time: datetime
    total_hours: float
    efficiency_fallback_used: bool


def _read_legacy_field(obj: Any, field: str) -> Any:
    try:
        inspect.getattr_static(obj, field)
    except AttributeError:
        return _MISSING
    return getattr(obj, field)


def _coerce_legacy_hours_value(raw_value: Any, *, field: str) -> float:
    if raw_value is _MISSING:
        return 0.0
    if raw_value is True:
        return 1.0
    if raw_value is False:
        return 0.0
    try:
        if not raw_value:
            return 0.0
    except Exception:
        raise
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"工时字段不合法：{field}={raw_value!r}") from exc


def validate_internal_hours(op: Any, batch: Any) -> float:
    setup_raw = _read_legacy_field(op, "setup_hours")
    unit_raw = _read_legacy_field(op, "unit_hours")
    quantity_raw = _read_legacy_field(batch, "quantity")

    setup_hours = _coerce_legacy_hours_value(setup_raw, field="setup_hours")
    unit_hours = _coerce_legacy_hours_value(unit_raw, field="unit_hours")
    quantity = _coerce_legacy_hours_value(quantity_raw, field="quantity")

    total_hours_base = float(setup_hours) + float(unit_hours) * float(quantity)
    if not math.isfinite(float(total_hours_base)) or float(total_hours_base) < 0:
        raise ValueError(
            "工时总量不合法："
            f"setup_hours={setup_raw!r} unit_hours={unit_raw!r} quantity={quantity_raw!r} total_hours_base={total_hours_base!r}"
        )
    return float(total_hours_base)


def validate_internal_hours_for_mode(op: Any, batch: Any, *, strict_mode: bool) -> float:
    try:
        return validate_internal_hours(op, batch)
    except ValueError as exc:
        if strict_mode:
            raise_strict_internal_hours_validation(op, batch, exc)
        raise


def raise_strict_internal_hours_validation(op: Any, batch: Any, exc: ValueError) -> None:
    for field, raw_value in _internal_hour_fields(op, batch):
        if raw_value is True:
            continue
        try:
            if not raw_value:
                continue
        except Exception:
            raise
        _raise_if_invalid_strict_number(field, raw_value)
    raise ValidationError(str(exc), field="setup_hours")


def _internal_hour_fields(op: Any, batch: Any) -> Tuple[Tuple[str, Any], ...]:
    return (
        ("setup_hours", getattr(op, "setup_hours", None)),
        ("unit_hours", getattr(op, "unit_hours", None)),
        ("quantity", getattr(batch, "quantity", None)),
    )


def _raise_if_invalid_strict_number(field: str, raw_value: Any) -> None:
    try:
        parsed = float(raw_value)
    except Exception as parse_exc:
        raise ValidationError(f"“{field}”必须是数字", field=field) from parse_exc
    if not math.isfinite(parsed):
        raise ValidationError(f"“{field}”必须是有限数字", field=field)
    if parsed < 0:
        raise ValidationError(f"“{field}”必须大于等于 0", field=field)


def _resolve_efficiency(
    calendar: Any,
    *,
    start_time: datetime,
    operator_id: str,
) -> Tuple[float, bool]:
    raw_eff = calendar.get_efficiency(start_time, operator_id=operator_id)
    if raw_eff is None:
        return 1.0, True
    try:
        eff = float(raw_eff)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"日历效率必须是数字：efficiency={raw_eff!r}", field="efficiency") from exc
    if not math.isfinite(eff):
        raise ValidationError(f"日历效率必须是有限数字：efficiency={raw_eff!r}", field="efficiency")
    if eff <= 0:
        raise ValidationError(f"日历效率必须大于 0：efficiency={raw_eff!r}", field="efficiency")
    return eff, False


def _changeover_penalty(op: Any, machine_id: str, last_op_type_by_machine: Optional[Mapping[str, str]]) -> int:
    if not last_op_type_by_machine:
        return 0
    current_type = str(getattr(op, "op_type_name", None) or "").strip()
    if not current_type:
        return 0
    last_type = str(last_op_type_by_machine.get(machine_id) or "").strip()
    if last_type and last_type != current_type:
        return 1
    return 0


def _abort_result(
    *,
    machine_id: str,
    operator_id: str,
    start_time: datetime,
    changeover_penalty: int,
    efficiency_fallback_used: bool,
) -> InternalSlotEstimate:
    return InternalSlotEstimate(
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=start_time,
        end_time=start_time,
        total_hours=0.0,
        changeover_penalty=changeover_penalty,
        abort_after_hit=True,
        efficiency_fallback_used=bool(efficiency_fallback_used),
    )


def _resolve_total_base(op: Any, batch: Any, total_hours_base: Optional[float]) -> float:
    total_base = validate_internal_hours(op, batch) if total_hours_base is None else float(total_hours_base)
    if not math.isfinite(total_base) or total_base < 0:
        raise ValueError(f"工时总量不合法：total_hours_base={total_base!r}")
    return total_base


def _slot_segments(
    *,
    machine_timeline: Sequence[Tuple[datetime, datetime]],
    operator_timeline: Sequence[Tuple[datetime, datetime]],
    machine_downtimes: Optional[Sequence[Tuple[datetime, datetime]]],
) -> Tuple[List[Tuple[datetime, datetime]], List[Tuple[datetime, datetime]], List[Tuple[datetime, datetime]]]:
    return list(machine_timeline or []), list(operator_timeline or []), list(machine_downtimes or [])


def _max_shift_count(segment_groups: Tuple[List[Tuple[datetime, datetime]], ...]) -> int:
    return max(sum(len(segments) for segments in segment_groups) + 1, 10)


def _adjust_slot_start(calendar: Any, start_time: datetime, *, priority: Any, operator_id: str) -> datetime:
    return calendar.adjust_to_working_time(start_time, priority=priority, operator_id=operator_id)


def _abort_after_result(
    *,
    earliest: datetime,
    abort_after: Optional[datetime],
    machine_id: str,
    operator_id: str,
    changeover_penalty: int,
    efficiency_fallback_used: bool,
) -> Optional[InternalSlotEstimate]:
    if abort_after is None or earliest <= abort_after:
        return None
    return _abort_result(
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=earliest,
        changeover_penalty=changeover_penalty,
        efficiency_fallback_used=efficiency_fallback_used,
    )


def _estimate_attempt(calendar: Any, *, earliest: datetime, total_base: float, priority: Any, operator_id: str) -> _SlotAttempt:
    eff, used_fallback = _resolve_efficiency(calendar, start_time=earliest, operator_id=operator_id)
    total_hours = float(total_base) / float(eff) if float(eff) != 1.0 else float(total_base)
    return _SlotAttempt(
        start_time=earliest,
        end_time=calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id),
        total_hours=float(total_hours),
        efficiency_fallback_used=bool(used_fallback),
    )


def _latest_overlap_shift_end(
    segment_groups: Tuple[List[Tuple[datetime, datetime]], ...],
    earliest: datetime,
    end_time: datetime,
) -> Optional[datetime]:
    candidates = [find_overlap_shift_end(segments, earliest, end_time) for segments in segment_groups]
    valid_candidates = [candidate for candidate in candidates if candidate is not None]
    return max(valid_candidates) if valid_candidates else None


def _shifted_start(calendar: Any, *, earliest: datetime, shift_to: datetime, priority: Any, operator_id: str) -> datetime:
    return _adjust_slot_start(calendar, max(earliest, shift_to), priority=priority, operator_id=operator_id)


def _build_slot_estimate(
    *,
    machine_id: str,
    operator_id: str,
    attempt: _SlotAttempt,
    changeover_penalty: int,
    end_dt_exclusive: Optional[datetime],
    efficiency_fallback_used: bool,
) -> InternalSlotEstimate:
    return InternalSlotEstimate(
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=attempt.start_time,
        end_time=attempt.end_time,
        total_hours=float(attempt.total_hours),
        changeover_penalty=changeover_penalty,
        blocked_by_window=bool(end_dt_exclusive is not None and attempt.end_time >= end_dt_exclusive),
        abort_after_hit=False,
        efficiency_fallback_used=efficiency_fallback_used,
    )


def estimate_internal_slot(
    *,
    calendar: Any,
    op: Any,
    batch: Any,
    machine_id: str,
    operator_id: str,
    base_time: datetime,
    prev_end: datetime,
    machine_timeline: Sequence[Tuple[datetime, datetime]],
    operator_timeline: Sequence[Tuple[datetime, datetime]],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Sequence[Tuple[datetime, datetime]]],
    last_op_type_by_machine: Optional[Mapping[str, str]],
    abort_after: Optional[datetime],
    total_hours_base: Optional[float] = None,
) -> InternalSlotEstimate:
    total_base = _resolve_total_base(op, batch, total_hours_base)
    priority = getattr(batch, "priority", None)
    changeover_penalty = _changeover_penalty(op, machine_id, last_op_type_by_machine)
    segment_groups = _slot_segments(
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        machine_downtimes=machine_downtimes,
    )
    max_shifts = _max_shift_count(segment_groups)

    earliest = max(prev_end, base_time)
    earliest = _adjust_slot_start(calendar, earliest, priority=priority, operator_id=operator_id)
    abort_result = _abort_after_result(
        earliest=earliest,
        abort_after=abort_after,
        machine_id=machine_id,
        operator_id=operator_id,
        changeover_penalty=changeover_penalty,
        efficiency_fallback_used=False,
    )
    if abort_result is not None:
        return abort_result

    shift_count = 0
    efficiency_fallback_used = False
    while True:
        attempt = _estimate_attempt(calendar, earliest=earliest, total_base=total_base, priority=priority, operator_id=operator_id)
        efficiency_fallback_used = bool(efficiency_fallback_used or attempt.efficiency_fallback_used)
        shift_to = _latest_overlap_shift_end(segment_groups, earliest, attempt.end_time)
        if shift_to is None:
            return _build_slot_estimate(
                machine_id=machine_id,
                operator_id=operator_id,
                attempt=attempt,
                changeover_penalty=changeover_penalty,
                end_dt_exclusive=end_dt_exclusive,
                efficiency_fallback_used=efficiency_fallback_used,
            )

        shift_count += 1
        if shift_count > max_shifts:
            raise RuntimeError(
                f"内部工序避让超出显式上界：machine_id={machine_id!r} operator_id={operator_id!r} max_shifts={max_shifts}"
            )
        earliest = _shifted_start(calendar, earliest=earliest, shift_to=shift_to, priority=priority, operator_id=operator_id)
        abort_result = _abort_after_result(
            earliest=earliest,
            abort_after=abort_after,
            machine_id=machine_id,
            operator_id=operator_id,
            changeover_penalty=changeover_penalty,
            efficiency_fallback_used=efficiency_fallback_used,
        )
        if abort_result is not None:
            return abort_result
