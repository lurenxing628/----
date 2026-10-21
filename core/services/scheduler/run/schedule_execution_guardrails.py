from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Set, Tuple

from core.errors import AppError, ErrorCode
from core.models import BatchOperation
from core.models.enums import SourceType
from core.models.operation_execution_event import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
)
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_ledger_guard import (
    ensure_ledger_execution_schedulable,
    fact_resource_segments,
)
from core.shared.local_datetime import parse_local_datetime as parse_dt

from .schedule_execution_resource_facts import collect_resource_execution_facts
from .schedule_input_seed_metadata import with_confirmed_merged_group_periods


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


def _planned_duration(schedule_row: Any, *, op_id: int) -> timedelta:
    raw_start = schedule_row.get("start_time") if isinstance(schedule_row, dict) else getattr(schedule_row, "start_time", None)
    raw_end = schedule_row.get("end_time") if isinstance(schedule_row, dict) else getattr(schedule_row, "end_time", None)
    start_time = parse_dt(raw_start)
    end_time = parse_dt(raw_end)
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
        end_time = actual_start_time + _planned_duration(schedule_row, op_id=op_id)

    if op.source == SourceType.EXTERNAL.value:
        if fact.actual_machine_id is not None or fact.actual_operator_id is not None:
            raise _execution_conflict("外协报工不能占用本厂设备或人员，请核对实际资源记录。",
                                      reason="external_actual_resource_conflict", op_id=op_id)
        machine_id, operator_id = None, None
    else:
        machine_id, operator_id = _execution_seed_resources(fact, op_id=op_id)
    result = {
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
        "op_type_id": getattr(op, "op_type_id", None),
        "seed_source": "execution_fact",
        "state_revision": fact.state_revision,
    }
    if fact.actual_status == EXECUTION_STATUS_COMPLETED and op.source != SourceType.EXTERNAL.value:
        segments = fact_resource_segments(fact)
        if len(segments) > 1:
            result["_resource_segments"] = segments
    return result


def _build_execution_seed_results(
    *,
    op_by_id: Dict[int, BatchOperation],
    facts: Dict[int, ExecutionFact],
    guarded_op_ids: Set[int],
    plan_rows,
    group_identities,
) -> List[Dict[str, Any]]:
    execution_seed_results: List[Dict[str, Any]] = []
    for op_id in sorted(guarded_op_ids):
        op = op_by_id.get(int(op_id))
        row = plan_rows.get(op_id)
        if op is None or row is None:
            raise _execution_conflict(
                "现场已经有开工或完工记录，但上一版正式排程里找不到对应工序，本次没有写入新排程。请刷新后重新排。",
                reason="missing_previous_schedule_row",
                op_id=op_id,
            )
        execution_seed_results.append(
            _build_execution_seed_result(
                fact=facts[int(op_id)],
                op=op,
                schedule_row=row,
            )
        )
    completed = {op_id for op_id in guarded_op_ids if facts[op_id].actual_status == EXECUTION_STATUS_COMPLETED}
    if not any(seed["source"] == SourceType.EXTERNAL.value and seed["op_id"] in completed for seed in execution_seed_results):
        return execution_seed_results
    return with_confirmed_merged_group_periods(execution_seed_results, group_identities=group_identities,
                                             completed_op_ids=completed)


def build_execution_guardrails_from_projections(svc, operations, *, prev_version, execution_projections, facts, external_groups):
    """Consume an explicit AJ snapshot without reloading or reaggregating reports."""
    if execution_projections is None:
        raise ValueError("必须显式传入 AJ 执行投影；无事实时传空列表。")
    if prev_version not in facts.resource_execution:
        facts.resource_execution[prev_version] = collect_resource_execution_facts(
            svc, prev_version=prev_version, execution_projections=execution_projections, capture=facts.capture,
            ledger=getattr(facts, "execution_service", None))
    execution_facts, plan_rows, execution_snapshot = facts.resource_execution[prev_version]
    return _execution_guardrail_tuple(operations, execution_facts, execution_snapshot,
                                     plan_rows=plan_rows, group_identities=external_groups)


def _execution_guardrail_tuple(operations, facts, execution_snapshot, *, plan_rows, group_identities):
    op_by_id: Dict[int, BatchOperation] = {_op_id(op): op for op in operations if _op_id(op) > 0}
    ensure_ledger_execution_schedulable(facts)
    fixed_op_ids: Set[int] = set()
    completed_op_ids: Set[int] = set()
    exception_op_ids: Set[int] = set()
    for op_id, fact in facts.items():
        op_id = int(op_id)
        status = str(fact.actual_status or "").strip().lower()
        if status == EXECUTION_STATUS_EXCEPTION:
            exception_op_ids.add(op_id)
        elif op_id in op_by_id:
            if status in (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED):
                fixed_op_ids.add(op_id)
            elif status == EXECUTION_STATUS_COMPLETED:
                completed_op_ids.add(op_id)
    if exception_op_ids:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "存在异常中的工序，请先处理现场异常后再重新排程。本次没有写入新排程。",
            details={"reason": "execution_exception_blocks_auto_reschedule", "op_ids": sorted(exception_op_ids)},
        )
    guarded_op_ids = fixed_op_ids | completed_op_ids
    if not guarded_op_ids:
        return facts, set(), set(), [], execution_snapshot

    execution_seed_results = _build_execution_seed_results(
        op_by_id=op_by_id,
        facts=facts,
        guarded_op_ids=guarded_op_ids,
        plan_rows=plan_rows,
        group_identities=group_identities,
    )
    return facts, fixed_op_ids, completed_op_ids, execution_seed_results, execution_snapshot
