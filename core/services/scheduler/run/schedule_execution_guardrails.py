from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Set, Tuple

from core.infrastructure.errors import AppError, ErrorCode
from core.models import BatchOperation
from core.models.enums import SourceType
from core.models.operation_execution_event import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
)
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
from core.services.scheduler.execution.execution_snapshot import ExecutionSnapshot

from .schedule_execution_resource_facts import collect_resource_execution_facts


def _op_id(op: Any) -> int:
    try:
        return int(getattr(op, "id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _execution_conflict(message: str, *, reason: str, op_id: int) -> AppError:
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        message,
        details={"reason": reason, "op_id": int(op_id)},
    )


def _planned_duration(schedule_row: Any, svc: Any, *, op_id: int) -> timedelta:
    start_time = svc._normalize_datetime(getattr(schedule_row, "start_time", None))
    end_time = svc._normalize_datetime(getattr(schedule_row, "end_time", None))
    if start_time is None or end_time is None or end_time <= start_time:
        raise _execution_conflict(
            "生产中的工序需要沿用上一版计划时长，但上一版排程时间不完整，本次没有写入新排程。请刷新排程数据后重试。",
            reason="invalid_previous_schedule_time",
            op_id=op_id,
        )
    return end_time - start_time


def _execution_seed_resources(fact: ExecutionFact, *, op_id: int) -> Tuple[str, str]:
    machine_id = str(fact.actual_machine_id or "").strip()
    operator_id = str(fact.actual_operator_id or "").strip()
    if not machine_id or not operator_id:
        raise _execution_conflict(
            "生产中或已完工的工序缺少实际设备或人员，本次没有写入新排程。请先核对现场反馈记录。",
            reason="missing_actual_resource",
            op_id=op_id,
        )
    return machine_id, operator_id


def _build_execution_seed_result(
    svc: Any,
    *,
    fact: ExecutionFact,
    op: BatchOperation,
    schedule_row: Any,
) -> Dict[str, Any]:
    op_id = int(fact.op_id)
    actual_start_time = fact.actual_start_time
    if actual_start_time is None:
        raise _execution_conflict(
            "生产中或已完工的工序缺少实际开工时间，本次没有写入新排程。请先核对现场反馈记录。",
            reason="missing_actual_start_time",
            op_id=op_id,
        )
    if fact.actual_status == EXECUTION_STATUS_COMPLETED:
        actual_end_time = fact.actual_end_time
        if actual_end_time is None or actual_end_time <= actual_start_time:
            raise _execution_conflict(
                "已完工的工序缺少有效完工时间，本次没有写入新排程。请先核对现场反馈记录。",
                reason="missing_actual_end_time",
                op_id=op_id,
            )
        end_time = actual_end_time
    else:
        end_time = actual_start_time + _planned_duration(schedule_row, svc, op_id=op_id)

    machine_id, operator_id = _execution_seed_resources(fact, op_id=op_id)
    return {
        "op_id": op_id,
        "op_code": getattr(op, "op_code", None),
        "batch_id": getattr(op, "batch_id", None),
        "seq": int(getattr(op, "seq", 0) or 0),
        "machine_id": machine_id,
        "operator_id": operator_id,
        "start_time": actual_start_time,
        "end_time": end_time,
        "source": str(getattr(op, "source", None) or SourceType.INTERNAL.value).strip(),
        "op_type_name": getattr(op, "op_type_name", None),
        "seed_source": "execution_fact",
        "state_revision": fact.state_revision,
    }


def _execution_status_op_ids(facts: Dict[int, ExecutionFact], statuses: Tuple[str, ...]) -> Set[int]:
    normalized_statuses = {str(status).strip().lower() for status in statuses}
    return {
        int(op_id)
        for op_id, fact in facts.items()
        if str(fact.actual_status or "").strip().lower() in normalized_statuses
    }


def _raise_if_exception_facts(facts: Dict[int, ExecutionFact]) -> None:
    exception_op_ids = _execution_status_op_ids(facts, (EXECUTION_STATUS_EXCEPTION,))
    if exception_op_ids:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "存在异常中的工序，请先处理现场异常后再重新排程。本次没有写入新排程。",
            details={"reason": "execution_exception_blocks_auto_reschedule", "op_ids": sorted(exception_op_ids)},
        )


def _build_execution_seed_results(
    svc: Any,
    *,
    op_by_id: Dict[int, BatchOperation],
    facts: Dict[int, ExecutionFact],
    guarded_op_ids: Set[int],
) -> List[Dict[str, Any]]:
    execution_seed_results: List[Dict[str, Any]] = []
    for op_id in sorted(guarded_op_ids):
        op = op_by_id.get(int(op_id))
        row = svc.schedule_repo.get(int(facts[op_id].schedule_id or 0))
        if op is None or row is None:
            raise _execution_conflict(
                "现场已经有开工或完工记录，但上一版正式排程里找不到对应工序，本次没有写入新排程。请刷新后重新排。",
                reason="missing_previous_schedule_row",
                op_id=op_id,
            )
        execution_seed_results.append(
            _build_execution_seed_result(
                svc,
                fact=facts[int(op_id)],
                op=op,
                schedule_row=row,
            )
        )
    return execution_seed_results


def _collect_execution_guardrails(
    svc: Any,
    operations: List[BatchOperation],
    *,
    prev_version: int,
) -> Tuple[Dict[int, ExecutionFact], Set[int], Set[int], List[Dict[str, Any]], Dict[int, str], ExecutionSnapshot]:
    facts, _, execution_snapshot = collect_resource_execution_facts(svc, prev_version=prev_version)
    return _execution_guardrail_tuple(svc, operations, facts, execution_snapshot)


def build_execution_guardrails_from_projections(svc, operations, *, prev_version, execution_projections):
    """Consume an explicit AJ snapshot without reloading or reaggregating reports."""
    if execution_projections is None:
        raise ValueError("必须显式传入 AJ 执行投影；无事实时传空列表。")
    facts, _, execution_snapshot = collect_resource_execution_facts(
        svc, prev_version=prev_version, execution_projections=execution_projections,
    )
    return _execution_guardrail_tuple(svc, operations, facts, execution_snapshot)


def _execution_guardrail_tuple(svc, operations, facts, execution_snapshot):
    op_by_id: Dict[int, BatchOperation] = {_op_id(op): op for op in operations if _op_id(op) > 0}
    ensure_ledger_execution_schedulable(facts)
    fixed_op_ids = _execution_status_op_ids(facts, (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED)) & set(op_by_id)
    completed_op_ids = _execution_status_op_ids(facts, (EXECUTION_STATUS_COMPLETED,)) & set(op_by_id)
    _raise_if_exception_facts(facts)
    guarded_op_ids = set(fixed_op_ids) | set(completed_op_ids)
    all_revisions = {
        int(op_id): fact.state_revision
        for op_id, fact in facts.items()
    }
    if not guarded_op_ids:
        return facts, set(), set(), [], all_revisions, execution_snapshot

    execution_seed_results = _build_execution_seed_results(
        svc,
        op_by_id=op_by_id,
        facts=facts,
        guarded_op_ids=guarded_op_ids,
    )
    return facts, fixed_op_ids, completed_op_ids, execution_seed_results, all_revisions, execution_snapshot
