from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple, cast

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
from core.errors import AppError, ErrorCode
from core.models.batch_operation import BatchOperation
from core.models.enums import SourceType
from core.models.operation_execution_scope import EXECUTION_STATUS_COMPLETED
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_ledger_guard import (
    ensure_ledger_execution_schedulable,
    fact_resource_segments,
)

from .schedule_execution_resource_facts import collect_resource_execution_facts
from .schedule_payload_contract import arrangement_row


def _execution_conflict(message: str, *, reason: str, op_id: int) -> AppError:
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        message,
        details={"reason": reason, "op_id": int(op_id)},
    )


def _execution_seed_resources(fact: ExecutionFact, *, op_id: int) -> Tuple[str, str]:
    machine_id = str(fact.actual_machine_id or "").strip()
    operator_id = str(fact.actual_operator_id or "").strip()
    if not machine_id or not operator_id:
        raise _execution_conflict(
            "已完工的工序缺少实际设备或人员，本次没有写入新排程。请先核对现场反馈记录。",
            reason="missing_actual_resource",
            op_id=op_id,
        )
    return machine_id, operator_id


def _build_execution_seed_result(
    *,
    fact: ExecutionFact,
    op: BatchOperation,
) -> Dict[str, Any]:
    op_id = fact.op_id
    actual_start_time = fact.actual_start_time
    if actual_start_time is None:
        raise _execution_conflict(
            "已完工的工序缺少实际开工时间，本次没有写入新排程。请先核对现场反馈记录。",
            reason="missing_actual_start_time",
            op_id=op_id,
        )
    actual_end_time = fact.actual_end_time
    if actual_end_time is None or actual_end_time < actual_start_time:
        raise _execution_conflict(
            "已完工的工序缺少有效完工时间，本次没有写入新排程。请先核对现场反馈记录。",
            reason="missing_actual_end_time",
            op_id=op_id,
        )
    end_time = actual_end_time

    if op.source == SourceType.EXTERNAL.value:
        if fact.actual_machine_id is not None or fact.actual_operator_id is not None:
            raise _execution_conflict("外协报工不能占用本厂设备或人员，请核对实际资源记录。",
                                      reason="external_actual_resource_conflict", op_id=op_id)
        machine_id, operator_id = None, None
    else:
        machine_id, operator_id = _execution_seed_resources(fact, op_id=op_id)
    result = {
        "op_id": op_id,
        "op_code": op.op_code,
        "batch_id": op.batch_id,
        "seq": op.seq,
        "machine_id": machine_id,
        "operator_id": operator_id,
        "start_time": actual_start_time,
        "end_time": end_time,
        "source": op.source,
        "op_type_name": op.op_type_name,
        "op_type_id": op.op_type_id,
        "seed_source": "execution_fact",
        "state_revision": fact.state_revision,
    }
    if end_time == actual_start_time:
        if (
            op.source != SourceType.INTERNAL.value
            or fact.ledger_operation_ref is None
            or fact.target_quantity is None
        ):
            raise _execution_conflict(
                "已完工的工序缺少有效完工时间，本次没有写入新排程。请先核对现场反馈记录。",
                reason="missing_actual_end_time",
                op_id=op_id,
            )
        witness = SchedulePointEvidence(
            op_id=op_id,
            machine_id=cast(str, machine_id),
            operator_id=cast(str, operator_id),
            at=actual_start_time,
            setup_hours=op.setup_hours,
            unit_hours=op.unit_hours,
            quantity=fact.target_quantity,
        )
        if not witness.matches(arrangement_row(result)):
            raise _execution_conflict(
                "已完工的工序缺少有效完工时间，本次没有写入新排程。请先核对现场反馈记录。",
                reason="missing_actual_end_time",
                op_id=op_id,
            )
        result["_point_evidence"] = witness
    if op.source != SourceType.EXTERNAL.value:
        segments = fact_resource_segments(fact)
        if segments:
            result["_resource_segments"] = segments
    return result


def _build_execution_seed_results(
    *,
    op_by_id: Dict[int, BatchOperation],
    facts: Dict[int, ExecutionFact],
    completed_op_ids: Set[int],
    plan_rows,
) -> List[Dict[str, Any]]:
    execution_seed_results: List[Dict[str, Any]] = []
    for op_id in sorted(completed_op_ids):
        op = op_by_id.get(int(op_id))
        row = plan_rows.get(op_id)
        if op is None or row is None:
            raise _execution_conflict(
                "现场已经有完工记录，但上一版正式排程里找不到对应工序，本次没有写入新排程。请刷新后重新排。",
                reason="missing_previous_schedule_row",
                op_id=op_id,
            )
        execution_seed_results.append(
            _build_execution_seed_result(
                fact=facts[int(op_id)],
                op=op,
            )
        )
    return execution_seed_results


def build_execution_guardrails_from_projections(conn, operations, *, prev_version, execution_projections, facts):
    """Consume an explicit AJ snapshot without reloading or reaggregating reports."""
    if execution_projections is None:
        raise ValueError("必须显式传入 AJ 执行投影；无事实时传空列表。")
    if prev_version not in facts.resource_execution:
        facts.resource_execution[prev_version] = collect_resource_execution_facts(
            conn, prev_version=prev_version, execution_projections=execution_projections, capture=facts.capture,
            ledger=facts.execution_service)
    execution_facts, plan_rows, execution_snapshot = facts.resource_execution[prev_version]
    return _execution_guardrail_tuple(operations, execution_facts, execution_snapshot,
                                     plan_rows=plan_rows)


def _execution_guardrail_tuple(operations, facts, execution_snapshot, *, plan_rows):
    op_by_id: Dict[int, BatchOperation] = {op.id: op for op in operations if op.id > 0}
    ensure_ledger_execution_schedulable(facts)
    completed_op_ids: Set[int] = {
        int(op_id)
        for op_id, fact in facts.items()
        if int(op_id) in op_by_id and fact.actual_status == EXECUTION_STATUS_COMPLETED
    }
    if not completed_op_ids:
        return facts, set(), [], execution_snapshot

    execution_seed_results = _build_execution_seed_results(
        op_by_id=op_by_id,
        facts=facts,
        completed_op_ids=completed_op_ids,
        plan_rows=plan_rows,
    )
    return facts, completed_op_ids, execution_seed_results, execution_snapshot
