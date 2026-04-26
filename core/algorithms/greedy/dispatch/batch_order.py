from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.ordering import normalize_text_id
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import EXTERNAL, INTERNAL
from core.infrastructure.errors import ValidationError

from ..run_context import ensure_run_context
from ..run_state import ScheduleRunState

_SCHEDULE_OPERATION_FAILED_MESSAGE = "排产异常，请查看系统日志。"


def dispatch_batch_order(
    context: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: Optional[ScheduleRunState] = None,
    batch_progress: Optional[Dict[str, datetime]] = None,
    external_group_cache: Optional[Dict[Tuple[str, str], Tuple[datetime, datetime]]] = None,
    machine_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    operator_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    machine_busy_hours: Optional[Dict[str, float]] = None,
    operator_busy_hours: Optional[Dict[str, float]] = None,
    last_op_type_by_machine: Optional[Dict[str, str]] = None,
    last_end_by_machine: Optional[Dict[str, datetime]] = None,
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    results: Optional[List[ScheduleResult]] = None,
    errors: Optional[List[str]] = None,
    blocked_batches: Optional[set] = None,
    scheduled_count: int = 0,
    failed_count: int = 0,
    strict_mode: bool = False,
) -> Tuple[int, int]:
    ctx = ensure_run_context(context)
    run_state = _coerce_state(
        state=state,
        base_time=base_time,
        batch_progress=batch_progress,
        external_group_cache=external_group_cache,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        last_op_type_by_machine=last_op_type_by_machine,
        last_end_by_machine=last_end_by_machine,
        results=results,
        errors=errors,
        blocked_batches=blocked_batches,
        scheduled_count=scheduled_count,
        failed_count=failed_count,
    )
    for op in sorted_ops:
        _dispatch_one(
            ctx,
            state=run_state,
            op=op,
            batches=batches,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            strict_mode=bool(strict_mode),
        )
    _ = scheduled_count
    return run_state.scheduled_count, run_state.failed_count


def _coerce_state(
    *,
    state: Optional[ScheduleRunState],
    base_time: datetime,
    batch_progress: Optional[Dict[str, datetime]],
    external_group_cache: Optional[Dict[Tuple[str, str], Tuple[datetime, datetime]]],
    machine_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    operator_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    machine_busy_hours: Optional[Dict[str, float]],
    operator_busy_hours: Optional[Dict[str, float]],
    last_op_type_by_machine: Optional[Dict[str, str]],
    last_end_by_machine: Optional[Dict[str, datetime]],
    results: Optional[List[ScheduleResult]],
    errors: Optional[List[str]],
    blocked_batches: Optional[set],
    scheduled_count: int,
    failed_count: int,
) -> ScheduleRunState:
    if state is not None:
        return state
    return ScheduleRunState.from_legacy(
        base_time=base_time,
        batch_progress=batch_progress if batch_progress is not None else {},
        external_group_cache=external_group_cache if external_group_cache is not None else {},
        machine_timeline=machine_timeline if machine_timeline is not None else {},
        operator_timeline=operator_timeline if operator_timeline is not None else {},
        machine_busy_hours=machine_busy_hours if machine_busy_hours is not None else {},
        operator_busy_hours=operator_busy_hours if operator_busy_hours is not None else {},
        last_op_type_by_machine=last_op_type_by_machine if last_op_type_by_machine is not None else {},
        last_end_by_machine=last_end_by_machine if last_end_by_machine is not None else {},
        results=results if results is not None else [],
        errors=errors if errors is not None else [],
        blocked_batches=blocked_batches if blocked_batches is not None else set(),
        scheduled_count=scheduled_count,
        failed_count=failed_count,
    )


def _dispatch_one(
    ctx: Any,
    *,
    state: ScheduleRunState,
    op: Any,
    batches: Dict[str, Any],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
) -> None:
    batch_id = ""
    try:
        batch_id = normalize_text_id(getattr(op, "batch_id", ""))
        if not _validate_batch(op=op, batch_id=batch_id, batches=batches, state=state):
            return
        result, _blocked = _schedule_op(
            ctx,
            op=op,
            batch=batches[batch_id],
            state=state,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            strict_mode=strict_mode,
        )
        if result and result.start_time and result.end_time:
            state.record_dispatch_success(result)
        else:
            state.record_dispatch_failure(batch_id, block=True)
    except ValidationError:
        raise
    except Exception:
        _record_dispatch_exception(ctx, op=op, batch_id=batch_id, state=state)


def _validate_batch(*, op: Any, batch_id: str, batches: Dict[str, Any], state: ScheduleRunState) -> bool:
    if batch_id not in batches:
        state.failed_count += 1
        state.errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {batch_id}")
        return False
    if batch_id in state.blocked_batches:
        state.failed_count += 1
        return False
    return True


def _schedule_op(
    ctx: Any,
    *,
    op: Any,
    batch: Any,
    state: ScheduleRunState,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
):
    if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == EXTERNAL:
        return ctx.schedule_external(
            op=op,
            batch=batch,
            batch_progress=state.batch_progress,
            external_group_cache=state.external_group_cache,
            base_time=base_time,
            errors=state.errors,
            end_dt_exclusive=end_dt_exclusive,
            strict_mode=strict_mode,
        )
    return ctx.schedule_internal(
        op=op,
        batch=batch,
        batch_progress=state.batch_progress,
        machine_timeline=state.machine_timeline,
        operator_timeline=state.operator_timeline,
        base_time=base_time,
        errors=state.errors,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
        last_op_type_by_machine=state.last_op_type_by_machine,
        machine_busy_hours=state.machine_busy_hours,
        operator_busy_hours=state.operator_busy_hours,
        strict_mode=strict_mode,
    )


def _record_dispatch_exception(ctx: Any, *, op: Any, batch_id: str, state: ScheduleRunState) -> None:
    state.failed_count += 1
    op_code = getattr(op, "op_code", "-") or "-"
    state.errors.append(f"工序 {op_code} {_SCHEDULE_OPERATION_FAILED_MESSAGE}")
    ctx.log_exception(f"工序 {op_code} 排产异常")
    if batch_id:
        state.blocked_batches.add(batch_id)
