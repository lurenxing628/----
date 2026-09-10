from __future__ import annotations

from typing import Dict, Set

from core.infrastructure.errors import AppError, ErrorCode
from core.models.operation_execution_event import EXECUTION_STATUS_PAUSED, EXECUTION_STATUS_PROCESSING
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact


def ensure_execution_feedback_publishable(
    facts: Dict[int, ExecutionFact], *, selected_op_ids: Set[int], simulate: bool,
) -> None:
    if simulate:
        return
    unselected_live = {
        op_id: fact for op_id, fact in facts.items()
        if op_id not in selected_op_ids
        and fact.actual_status in (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED)
    }
    if not unselected_live:
        return
    batches = sorted({str(fact.batch_id) for fact in unselected_live.values()})
    # Only the omitted live-work boundary belongs to this guard. Preserve the
    # existing selected-work path without promising cross-version event transfer.
    raise AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "未选中的在制批次（" + "、".join(batches[:10]) + "）不能安全发布：新方案不包含这些工序，"
        "会使原现场记录失去继续报工入口。本次未发布；请先在当前正式方案中完成这些批次的现场报工，或仅做模拟排程。",
        details={
            "reason": "execution_feedback_continuity_blocks_publish",
            "op_ids": sorted(unselected_live),
            "batch_ids": batches,
            "unselected_batch_ids": batches,
        },
    )
