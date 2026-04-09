from __future__ import annotations

import inspect
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence, Tuple

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


def _resolve_efficiency(
    calendar: Any,
    *,
    start_time: datetime,
    operator_id: str,
) -> Tuple[float, bool]:
    raw_eff = calendar.get_efficiency(start_time, operator_id=operator_id)
    if raw_eff is None:
        return 1.0, True
    eff = float(raw_eff)
    if (not math.isfinite(eff)) or eff <= 0:
        return 1.0, True
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
    total_base = validate_internal_hours(op, batch) if total_hours_base is None else float(total_hours_base)
    if not math.isfinite(total_base) or total_base < 0:
        raise ValueError(f"工时总量不合法：total_hours_base={total_base!r}")

    priority = getattr(batch, "priority", None)
    changeover_penalty = _changeover_penalty(op, machine_id, last_op_type_by_machine)
    machine_segments = list(machine_timeline or [])
    operator_segments = list(operator_timeline or [])
    downtime_segments = list(machine_downtimes or [])
    max_shifts = max(len(machine_segments) + len(operator_segments) + len(downtime_segments) + 1, 10)

    earliest = max(prev_end, base_time)
    earliest = calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)
    if abort_after is not None and earliest > abort_after:
        return _abort_result(
            machine_id=machine_id,
            operator_id=operator_id,
            start_time=earliest,
            changeover_penalty=changeover_penalty,
            efficiency_fallback_used=False,
        )

    shift_count = 0
    efficiency_fallback_used = False
    while True:
        eff, used_fallback = _resolve_efficiency(calendar, start_time=earliest, operator_id=operator_id)
        efficiency_fallback_used = bool(efficiency_fallback_used or used_fallback)
        total_hours = float(total_base) / float(eff) if float(eff) != 1.0 else float(total_base)
        end_time = calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)

        shift_to = None
        for candidate in (
            find_overlap_shift_end(machine_segments, earliest, end_time),
            find_overlap_shift_end(operator_segments, earliest, end_time),
            find_overlap_shift_end(downtime_segments, earliest, end_time),
        ):
            if candidate is None:
                continue
            if shift_to is None or candidate > shift_to:
                shift_to = candidate
        if shift_to is None:
            break

        shift_count += 1
        if shift_count > max_shifts:
            raise RuntimeError(
                f"内部工序避让超出显式上界：machine_id={machine_id!r} operator_id={operator_id!r} max_shifts={max_shifts}"
            )
        earliest = max(earliest, shift_to)
        earliest = calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)
        if abort_after is not None and earliest > abort_after:
            return _abort_result(
                machine_id=machine_id,
                operator_id=operator_id,
                start_time=earliest,
                changeover_penalty=changeover_penalty,
                efficiency_fallback_used=efficiency_fallback_used,
            )

    return InternalSlotEstimate(
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=earliest,
        end_time=end_time,
        total_hours=float(total_hours),
        changeover_penalty=changeover_penalty,
        blocked_by_window=bool(end_dt_exclusive is not None and end_time >= end_dt_exclusive),
        abort_after_hit=False,
        efficiency_fallback_used=efficiency_fallback_used,
    )
