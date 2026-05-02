from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.ordering import normalize_text_id
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import INTERNAL

from .algo_stats import increment_counter
from .downtime import occupy_resource
from .internal_slot import estimate_internal_slot, raise_strict_internal_hours_validation


def schedule_internal_operation(
    *,
    calendar: Any,
    algo_stats: Any,
    auto_assign_resources: Any,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    errors: List[str],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    auto_assign_enabled: bool = False,
    resource_pool: Optional[Dict[str, Any]] = None,
    last_op_type_by_machine: Optional[Dict[str, str]] = None,
    machine_busy_hours: Optional[Dict[str, float]] = None,
    operator_busy_hours: Optional[Dict[str, float]] = None,
    strict_mode: bool = False,
) -> Tuple[Optional[ScheduleResult], bool]:
    bid = normalize_text_id(getattr(op, "batch_id", ""))
    machine_id, operator_id = _resolve_internal_resources(
        algo_stats=algo_stats,
        auto_assign_resources=auto_assign_resources,
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
        last_op_type_by_machine=last_op_type_by_machine or {},
        machine_busy_hours=machine_busy_hours or {},
        operator_busy_hours=operator_busy_hours or {},
        errors=errors,
    )
    if not machine_id or not operator_id:
        return None, False

    estimate = _estimate_internal(
        calendar=calendar,
        op=op,
        batch=batch,
        bid=bid,
        machine_id=machine_id,
        operator_id=operator_id,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        last_op_type_by_machine=last_op_type_by_machine,
        errors=errors,
        strict_mode=bool(strict_mode),
    )
    if estimate is None:
        return None, False
    if estimate.blocked_by_window:
        errors.append(_window_blocked_error(op=op, batch_id=bid, end_time=estimate.end_time, end_dt_exclusive=end_dt_exclusive))
        return None, True

    occupy_resource(machine_timeline, machine_id, estimate.start_time, estimate.end_time)
    occupy_resource(operator_timeline, operator_id, estimate.start_time, estimate.end_time)
    if estimate.efficiency_fallback_used:
        increment_counter(algo_stats, "internal_efficiency_fallback_count")
    return _build_internal_result(op=op, batch_id=bid, machine_id=machine_id, operator_id=operator_id, estimate=estimate), False


def _resolve_internal_resources(
    *,
    algo_stats: Any,
    auto_assign_resources: Any,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    errors: List[str],
) -> Tuple[str, str]:
    machine_id = normalize_text_id(getattr(op, "machine_id", None))
    operator_id = normalize_text_id(getattr(op, "operator_id", None))
    if machine_id and operator_id:
        return machine_id, operator_id
    if not auto_assign_enabled or resource_pool is None:
        increment_counter(algo_stats, "internal_missing_resource_without_auto_assign_count")
        errors.append(f"自制工序未补全设备或人员，无法排产：工序 {getattr(op, 'op_code', '-') or '-'}")
        return "", ""

    increment_counter(algo_stats, "internal_auto_assign_attempt_count")
    chosen = auto_assign_resources(
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
    )
    if chosen:
        increment_counter(algo_stats, "internal_auto_assign_success_count")
        return normalize_text_id(chosen[0]), normalize_text_id(chosen[1])
    increment_counter(algo_stats, "internal_auto_assign_failed_count")
    errors.append(f"自制工序未补全设备或人员，而且系统自动分配也失败了：工序 {getattr(op, 'op_code', '-') or '-'}")
    return "", ""


def _estimate_internal(
    *,
    calendar: Any,
    op: Any,
    batch: Any,
    bid: str,
    machine_id: str,
    operator_id: str,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    last_op_type_by_machine: Optional[Dict[str, str]],
    errors: List[str],
    strict_mode: bool,
):
    try:
        estimate = estimate_internal_slot(
            calendar=calendar,
            op=op,
            batch=batch,
            machine_id=machine_id,
            operator_id=operator_id,
            base_time=base_time,
            prev_end=batch_progress.get(bid, base_time),
            machine_timeline=machine_timeline.get(machine_id) or [],
            operator_timeline=operator_timeline.get(operator_id) or [],
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
            last_op_type_by_machine=last_op_type_by_machine,
            abort_after=None,
        )
    except ValueError as exc:
        if strict_mode:
            raise_strict_internal_hours_validation(op, batch, exc)
        errors.append(f"工时不合法：工序 {getattr(op, 'op_code', '-') or '-'} {exc}")
        return None
    if estimate.abort_after_hit:
        raise RuntimeError("正式内部排产不应命中 abort_after 早停")
    return estimate


def _window_blocked_error(*, op: Any, batch_id: str, end_time: datetime, end_dt_exclusive: Optional[datetime]) -> str:
    deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d") if end_dt_exclusive else "-"
    return (
        f"排产窗口截止到 {deadline}：自制工序 {getattr(op, 'op_code', '-') or '-'}"
        f"（批次 {batch_id}）预计完工 {end_time.strftime('%Y-%m-%d %H:%M')} 超出窗口"
    )


def _build_internal_result(*, op: Any, batch_id: str, machine_id: str, operator_id: str, estimate: Any) -> ScheduleResult:
    return ScheduleResult(
        op_id=int(getattr(op, "id", 0) or 0),
        op_code=str(getattr(op, "op_code", "") or ""),
        batch_id=batch_id,
        seq=int(getattr(op, "seq", 0) or 0),
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=estimate.start_time,
        end_time=estimate.end_time,
        source=INTERNAL,
        op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
    )
