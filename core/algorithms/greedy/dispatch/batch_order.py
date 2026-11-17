from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.resource_pool import ResourcePool
from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.run_state import ScheduleRunState

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch

    from .sgs_scoring import SgsCandidateScore


def dispatch_batch_order(
    ctx: Any,
    *,
    sorted_ops: List[OpForScheduleAlgo],
    batches: Dict[str, Batch],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: ScheduleRunState,
    resource_pool: ResourcePool,
) -> None:
    for op in sorted_ops:
        _dispatch_one(
            ctx,
            state=state,
            op=op,
            batches=batches,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            resource_pool=resource_pool,
        )


def _dispatch_one(
    ctx: Any,
    *,
    state: ScheduleRunState,
    op: OpForScheduleAlgo,
    batches: Dict[str, Batch],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    resource_pool: ResourcePool,
) -> None:
    batch_id = op.batch_id
    if batch_id in state.blocked_batches:
        state.record_skipped_after_batch_failure(op, batch_id)
        return
    result, failure = schedule_op(
        ctx,
        op=op,
        batch=batches[batch_id],
        state=state,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
    )
    if result is not None:
        state.record_dispatch_success(result)
    else:
        state.record_dispatch_failure(
            batch_id,
            failed_op=op,
            failure=failure,
        )


def schedule_op(
    ctx: Any,
    *,
    op: OpForScheduleAlgo,
    batch: Batch,
    state: ScheduleRunState,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    resource_pool: ResourcePool,
    scored: Optional[SgsCandidateScore] = None,
):
    if op.source == EXTERNAL:
        return ctx.schedule_external(
            op=op,
            batch_progress=state.batch_progress,
            external_group_cache=state.external_group_cache,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
        )
    work_batch = ctx.native_preparation.operation_batch(op, batch)
    return ctx.schedule_internal(
        op=op,
        batch=work_batch,
        batch_progress=state.batch_progress,
        machine_timeline=state.machine_timeline,
        operator_timeline=state.operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
        last_op_type_by_machine=state.last_op_type_by_machine,
        machine_busy_hours=state.machine_busy_hours,
        operator_busy_hours=state.operator_busy_hours,
        scored=scored,
    )
