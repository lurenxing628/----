"""One SGS pick: schedule the selected operation and do the success/failure bookkeeping."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_runtime.piece_input import operation_dispatch_state
from core.algorithm_runtime.run_state import ScheduleRunState

from .batch_order import schedule_op
from .sgs_graph import mark_graph_operation_completed
from .sgs_graph_failure import apply_graph_failure_bookkeeping

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch


def _dispatch_selected(
    ctx: Any,
    state: ScheduleRunState,
    op: OpForScheduleAlgo,
    batch_id: str,
    batches: Dict[str, Batch],
    next_idx: Dict[str, int],
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    graph_state: Optional[Dict[str, Any]] = None,
) -> None:
    from .sgs import resolve_operation_batch

    batch = resolve_operation_batch(ctx, op, batches[batch_id])
    errors_before = len(state.errors)
    result, _blocked = schedule_op(
        ctx,
        op=op,
        batch=batch,
        state=operation_dispatch_state(state, graph_state, op, batches[batch_id]),
        base_time=state.base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
    )
    if result and result.start_time and result.end_time:
        state.record_dispatch_success(result)
        next_idx[batch_id] += 1
        if graph_state is not None:
            if "end_time_by_op_id" in graph_state:
                graph_state["end_time_by_op_id"][op.id] = result.end_time
            mark_graph_operation_completed(graph_state, op.id)
        return
    extra_failed_count = 0
    if graph_state is None:
        # 非图模式：批内派工顺序就是列表顺序，按位置切片仍是正确口径（A04 保持不变）。
        skipped_ops = _remaining_ops_after(batch_id, next_idx, ops_by_batch)
    else:
        # 图模式：派工顺序跟随图链而非列表位置，被牵连集合按图状态推导（审计 A04）。
        skipped_ops, extra_failed_count = apply_graph_failure_bookkeeping(
            state,
            graph_state=graph_state,
            batch_id=batch_id,
            failed_op_id=op.id,
            ops_by_batch=ops_by_batch,
        )
    state.record_dispatch_failure(
        batch_id,
        block=True,
        remaining_failed=len(skipped_ops) + extra_failed_count,
        failed_op=op,
        skipped_ops=skipped_ops,
        error_message=(state.errors[-1] if len(state.errors) > errors_before else ""),
    )


def _remaining_ops_after(
    batch_id: str, next_idx: Dict[str, int], ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
) -> List[OpForScheduleAlgo]:
    return ops_by_batch[batch_id][next_idx[batch_id] + 1 :]
