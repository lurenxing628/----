from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.ordering import normalize_text_id
from core.algorithm_contracts.value_domains import EXTERNAL, INTERNAL
from core.algorithm_runtime.dispatch_context import DispatchContextContractError, ensure_dispatch_context
from core.algorithm_runtime.run_state import ScheduleRunState
from core.errors import ValidationError


def dispatch_batch_order(
    context: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: ScheduleRunState,
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool = False,
) -> Tuple[int, int]:
    ctx = ensure_dispatch_context(context)
    for op in sorted_ops:
        _dispatch_one(
            ctx,
            state=state,
            op=op,
            batches=batches,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            strict_mode=bool(strict_mode),
        )
    return state.scheduled_count, state.failed_count


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
            state.record_dispatch_failure(batch_id, block=True, failed_op=op)
    except (ValidationError, DispatchContextContractError):
        raise
    except Exception:
        _record_dispatch_exception(ctx, op=op, batch_id=batch_id, state=state)


def _validate_batch(*, op: Any, batch_id: str, batches: Dict[str, Any], state: ScheduleRunState) -> bool:
    if batch_id not in batches:
        state.record_missing_batch(op, batch_id)
        return False
    if batch_id in state.blocked_batches:
        state.record_skipped_after_batch_failure(op, batch_id)
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
    op_code = state._safe_text_attr(op, "op_code", "-") or "-"
    state.record_dispatch_exception(op, batch_id, dispatch_mode="batch_order")
    ctx.log_exception(f"工序 {op_code} 排产异常")
