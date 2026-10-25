from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from core.errors import AppError, ErrorCode
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.models.workbench_execution import ExecutionProjection
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


def _validate_event_plan_identities(capture) -> None:
    schedules = capture.index("Schedule", "id")
    operations = capture.index("BatchOperations", "id")
    for event in capture.table("OperationExecutionEvents"):
        if (event["source_table"] != SOURCE_SCHEDULE or event["effective_plan_role"] != ROLE_ADOPTED
                or event["scenario_id"] is not None):
            continue
        row, op = schedules.get(event["schedule_id"]), operations.get(event["op_id"])
        if (row is None or op is None or event["schedule_version"] != row["version"]
                or event["op_id"] != row["op_id"] or event["batch_id"] != op["batch_id"]):
            raise execution_conflict("execution_scope_missing")


def resource_execution_snapshot(
    facts: Dict[int, ExecutionFact], plan_rows: Dict[int, Dict[str, Any]],
) -> ExecutionSnapshot:
    return build_execution_snapshot(facts, sorted(facts), plan_rows=plan_rows)


def collect_resource_execution_facts(
    svc: Any, *, prev_version: int,
    execution_projections: Optional[Sequence[ExecutionProjection]] = None,
    capture, ledger=None,
) -> Tuple[Dict[int, ExecutionFact], Dict[int, Dict[str, Any]], ExecutionSnapshot]:
    try:
        _validate_event_plan_identities(capture)
        plan_rows = capture.latest_plan_rows(prev_version)
        facts = ExecutionFactProvider(svc.conn, logger=getattr(svc, "logger", None), capture=capture, ledger=ledger).facts_by_op_id_for_plan_rows(
            list(plan_rows.values()),
            {"source_table": SOURCE_SCHEDULE, "effective_plan_role": ROLE_ADOPTED, "scenario_id": None},
            include_op_ids=sorted(plan_rows),
            execution_projections=execution_projections,
        )
        snapshot = resource_execution_snapshot(facts, plan_rows)
    except (ValueError, TypeError, OverflowError) as exc:
        raise execution_conflict("invalid_execution_fact") from exc
    return facts, plan_rows, snapshot
