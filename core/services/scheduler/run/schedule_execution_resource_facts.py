from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from core.errors import AppError, ErrorCode
from core.models.workbench_execution import ExecutionProjection
from core.services.execution.ledger_reader import ExecutionLedgerReadScope
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution.execution_snapshot import (
    ExecutionSnapshot,
    build_execution_snapshot,
)


def execution_conflict(reason: str) -> AppError:
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场执行事实或正式计划身份不完整，本次没有写入新排程。请先核对现场反馈和正式计划。",
        details={"reason": reason},
    )


def collect_resource_execution_facts(
    *, prev_version: int,
    execution_projections: Sequence[ExecutionProjection],
    capture, ledger: ExecutionLedgerReadScope,
) -> Tuple[Dict[int, ExecutionFact], Dict[int, Dict[str, Any]], ExecutionSnapshot]:
    try:
        plan_rows = capture.latest_plan_rows(prev_version)
        facts = ExecutionFactProvider(ledger=ledger).facts_by_op_id_for_plan_rows(
            list(plan_rows.values()),
            execution_projections=execution_projections,
        )
        snapshot = build_execution_snapshot(facts, plan_rows=plan_rows)
    except (ValueError, TypeError, OverflowError) as exc:
        raise execution_conflict("invalid_execution_fact") from exc
    return facts, plan_rows, snapshot
