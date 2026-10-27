"""Graph-mode failure bookkeeping: block propagation, unreachable batch siblings and structured records."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from core.algorithm_runtime.run_state import ScheduleRunState
from core.errors import ValidationError

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo


def _block_graph_operation(graph_state: Dict[str, Any], op_id: int) -> Tuple[List[int], List[int]]:
    """阻塞失败工序及其尚未完成的待排后继，返回 (newly_blocked, fixed_conflicts)。

    - newly_blocked：本次新阻塞的待排工序（含失败工序自身）。
    - fixed_conflicts：传播撞到的"输入即固定"后继——即后道已报工（PROCESSING/
      PAUSED 进固定集）但前道排产失败的现场乱序报工形态（审计 A02）。这是
      可发生的生产输入，不再整趟 ValidationError 中止：固定工序现实中已执行，
      无需阻塞也不经它继续传播，由调用方按批失败留痕降级处理。
    - 传播撞到"本趟运行内已完成"的待排工序仍是内部不变量破坏（ready 队列要求
      前驱先完成，失败工序的后继不可能已完成），保持 fail-loud。
    """
    blocked = graph_state["blocked_op_ids"]
    successors_by_op_id = graph_state["successor_op_ids_by_op_id"]
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    input_fixed_op_ids = graph_state["input_fixed_op_ids"]
    newly_blocked: List[int] = []
    fixed_conflicts: List[int] = []
    stack = [op_id]
    while stack:
        current = stack.pop()
        if current in blocked:
            continue
        if current in completed_or_fixed:
            if current in input_fixed_op_ids:
                fixed_conflicts.append(current)
                continue
            raise ValidationError(
                f"图 ready 队列阻塞状态和固定/已完成工序冲突：{current}",
                field="graph_ready_context",
            )
        blocked.add(current)
        graph_state["ready_op_ids"].discard(current)
        newly_blocked.append(current)
        # Both graph-state builders key every known operation (sgs_graph._validate_graph_ready_links / topology).
        stack.extend(successors_by_op_id[current])
    return newly_blocked, sorted(set(fixed_conflicts))


def _graph_batch_unreachable_ops(
    graph_state: Dict[str, Any], batch_id: str, ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
) -> List[OpForScheduleAlgo]:
    """图模式失败簿记（审计 A04）：按图状态推导该批内"尚未完成且不再可达"的待排工序。

    替代旧的按列表位置切片（operations[idx0:]）——批内列表按 (seq,id) 排、图链按
    (seq,op_code,node_id) 排，同批同 seq（多 piece 合法形态）时两套 tie-break 错位
    会造成失败工序双记、已成功工序被记跳过、真被阻塞工序零留痕（scheduled+failed
    可超 total）。必须在 _block_graph_operation 之后调用：失败工序与图传播新阻塞的
    工序都已进入 blocked_op_ids，这里只补"图传播覆盖不到、但因批级阻塞不再可达"
    的剩余工序（例如固定后继下游的待排工序）。
    """
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    blocked_op_ids = graph_state["blocked_op_ids"]
    remaining: List[OpForScheduleAlgo] = []
    for op in ops_by_batch[batch_id]:
        if op.id in completed_or_fixed or op.id in blocked_op_ids:
            continue
        remaining.append(op)
    return remaining


def apply_graph_failure_bookkeeping(
    state: ScheduleRunState,
    *,
    graph_state: Dict[str, Any],
    batch_id: str,
    failed_op_id: int,
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
) -> Tuple[List[OpForScheduleAlgo], int]:
    """派工失败后的图侧记账：阻塞传播 + 图状态推导被牵连集合 + 结构化留痕。

    返回 (skipped_ops, extra_failed_count)：
    - skipped_ops：批级阻塞后不再可达的剩余工序，由调用方按
      skipped_after_batch_failure 记明细并计数；
    - extra_failed_count：图传播新阻塞工序（graph_blocked_after_failure 明细）的
      追加失败计数。失败工序自身由调用方计 1，不在两者之内，保证
      scheduled + failed <= total 且明细与真实一致（审计 A04）。
    """
    newly_blocked_op_ids, fixed_conflict_op_ids = _block_graph_operation(graph_state, failed_op_id)
    skipped_ops = _graph_batch_unreachable_ops(graph_state, batch_id, ops_by_batch)
    # Skipped operations never complete either, so their successors outside the batch are blocked too.
    fixed_conflicts = set(fixed_conflict_op_ids)
    for skipped_op in skipped_ops:
        skipped_blocked, skipped_conflicts = _block_graph_operation(graph_state, skipped_op.id)
        newly_blocked_op_ids.extend(skipped_blocked)
        fixed_conflicts.update(skipped_conflicts)
    fixed_conflict_op_ids = sorted(fixed_conflicts)
    extra_failed_count = _record_graph_blocked_operations(
        state,
        graph_state=graph_state,
        failed_op_id=failed_op_id,
        newly_blocked_op_ids=newly_blocked_op_ids,
        already_counted_op_ids={failed_op_id}.union(op.id for op in skipped_ops),
    )
    if fixed_conflict_op_ids:
        _record_graph_fixed_order_conflict(
            state,
            graph_state=graph_state,
            batch_id=batch_id,
            failed_op_id=failed_op_id,
            fixed_conflict_op_ids=fixed_conflict_op_ids,
        )
    return skipped_ops, extra_failed_count


def _record_graph_fixed_order_conflict(
    state: ScheduleRunState,
    *,
    graph_state: Dict[str, Any],
    batch_id: str,
    failed_op_id: int,
    fixed_conflict_op_ids: List[int],
) -> None:
    # 审计 A02：后道工序已报工/冻结（输入即固定）但前道排产失败——数据顺序异常。
    # 按批失败留痕（不中止整趟）：给失败工序追加一条结构化明细并写清冲突的固定
    # 后继 op_id，业务侧据此核对报工顺序；渲染文案见
    # core/models/scheduler_public_errors._structured_failure_message。
    _failed_batch_id, failed_op = graph_state["op_by_id"][failed_op_id]
    state.record_graph_fixed_order_conflict(
        failed_op,
        batch_id,
        fixed_successor_op_ids=fixed_conflict_op_ids,
    )


def _record_graph_blocked_operations(
    state: ScheduleRunState,
    *,
    graph_state: Dict[str, Any],
    failed_op_id: int,
    newly_blocked_op_ids: List[int],
    already_counted_op_ids: set,
) -> int:
    extra_failed_count = 0
    _failed_batch_id, failed_op = graph_state["op_by_id"][failed_op_id]
    for blocked_op_id in sorted(newly_blocked_op_ids):
        if blocked_op_id == failed_op_id:
            continue
        if blocked_op_id in already_counted_op_ids:
            continue
        blocked_batch_id, blocked_op = graph_state["op_by_id"][blocked_op_id]
        state.record_graph_blocked_after_failure(blocked_op, blocked_batch_id, failed_op=failed_op)
        extra_failed_count += 1
    return extra_failed_count
