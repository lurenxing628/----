from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.dispatch_context import DispatchContextContractError
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithm_runtime.run_state import ScheduleRunState
from core.errors import ValidationError

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch


def dispatch_batch_order(
    context: Any,
    *,
    sorted_ops: List[OpForScheduleAlgo],
    batches: Dict[str, Batch],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: ScheduleRunState,
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool = False,
) -> Tuple[int, int]:
    ctx = context
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
    op: OpForScheduleAlgo,
    batches: Dict[str, Batch],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
) -> None:
    batch_id = op.batch_id
    try:
        if not _validate_batch(op=op, batch_id=batch_id, batches=batches, state=state):
            return
        errors_before = len(state.errors)
        result, _blocked = schedule_op(
            ctx,
            op=op,
            batch=operation_batch(op, batches[batch_id]),
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
            state.record_dispatch_failure(
                batch_id,
                block=True,
                failed_op=op,
                error_message=(state.errors[-1] if len(state.errors) > errors_before else ""),
            )
    except (ValidationError, DispatchContextContractError):
        raise
    except Exception:
        _record_dispatch_exception(ctx, op=op, batch_id=batch_id, state=state)


def _validate_batch(*, op: OpForScheduleAlgo, batch_id: str, batches: Dict[str, Batch], state: ScheduleRunState) -> bool:
    if batch_id not in batches:
        state.record_missing_batch(op, batch_id)
        return False
    if batch_id in state.blocked_batches:
        state.record_skipped_after_batch_failure(op, batch_id)
        return False
    return True


def schedule_op(
    ctx: Any,
    *,
    op: OpForScheduleAlgo,
    batch: Batch,
    state: ScheduleRunState,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
):
    if op.source == EXTERNAL:
        return ctx.schedule_external(
            op=op,
            batch_progress=state.batch_progress,
            external_group_cache=state.external_group_cache,
            base_time=base_time,
            errors=state.errors,
            end_dt_exclusive=end_dt_exclusive,
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


def _record_dispatch_exception(ctx: Any, *, op: OpForScheduleAlgo, batch_id: str, state: ScheduleRunState) -> None:
    state.record_dispatch_exception(op, batch_id, dispatch_mode="batch_order")
    ctx.log_exception(f"工序 {op.op_code} 排产异常")
