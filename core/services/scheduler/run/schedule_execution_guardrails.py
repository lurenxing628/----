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
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution_snapshot import ExecutionSnapshot, build_execution_snapshot


def _op_id(op: Any) -> int:
    try:
        return int(getattr(op, "id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _schedule_row_op_id(row: Any) -> int:
    try:
        value = row.get("op_id") if isinstance(row, dict) else getattr(row, "op_id", 0)
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _execution_conflict(message: str, *, reason: str, op_id: int) -> AppError:
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        message,
        details={"reason": reason, "op_id": int(op_id)},
    )


def _schedule_rows_by_op_id(svc: Any, *, version: int, op_ids: Set[int]) -> Dict[int, Any]:
    rows: Dict[int, Any] = {}
    duplicates: Set[int] = set()
    for row in svc.schedule_repo.list_by_version(int(version)):
        op_id = _schedule_row_op_id(row)
        if op_id <= 0 or op_id not in op_ids:
            continue
        if op_id in rows:
            duplicates.add(op_id)
            continue
        rows[op_id] = row
    if duplicates:
        sample = "，".join(str(x) for x in sorted(duplicates)[:10])
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            f"上一版排程里同一道工序出现了重复记录（示例：{sample}），本次没有写入新排程。请刷新排程数据后重试。",
            details={"reason": "duplicate_previous_schedule_rows", "sample_op_ids": sorted(duplicates)[:10]},
        )
    return rows


def _plan_detail_rows_by_op_id(svc: Any, *, version: int, op_ids: Set[int]) -> Dict[int, Any]:
    if int(version or 0) <= 0 or not op_ids:
        return {}
    rows: Dict[int, Any] = {}
    duplicates: Set[int] = set()
    for row in svc.schedule_repo.list_by_version_with_details(int(version)):
        op_id = _schedule_row_op_id(row)
        if op_id <= 0 or op_id not in op_ids:
            continue
        if op_id in rows:
            duplicates.add(op_id)
            continue
        rows[op_id] = row
    if duplicates:
        sample = "，".join(str(x) for x in sorted(duplicates)[:10])
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            f"上一版排程里同一道工序出现了重复记录（示例：{sample}），本次没有写入新排程。请刷新排程数据后重试。",
            details={"reason": "duplicate_previous_schedule_rows", "sample_op_ids": sorted(duplicates)[:10]},
        )
    return rows


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
    prev_version: int,
) -> List[Dict[str, Any]]:
    schedule_rows = _schedule_rows_by_op_id(svc, version=int(prev_version), op_ids=guarded_op_ids)
    execution_seed_results: List[Dict[str, Any]] = []
    for op_id in sorted(guarded_op_ids):
        op = op_by_id.get(int(op_id))
        row = schedule_rows.get(int(op_id))
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
    op_by_id: Dict[int, BatchOperation] = {_op_id(op): op for op in operations if _op_id(op) > 0}
    plan_rows = _plan_detail_rows_by_op_id(svc, version=int(prev_version), op_ids=set(op_by_id))
    plan_op_ids = sorted(plan_rows)
    facts = ExecutionFactProvider(svc.conn, logger=getattr(svc, "logger", None)).facts_by_op_id_for_plan_rows(
        list(plan_rows.values()),
        {"version": int(prev_version), "source_table": SOURCE_SCHEDULE, "effective_plan_role": ROLE_ADOPTED},
        include_op_ids=plan_op_ids,
    )
    execution_snapshot = build_execution_snapshot(facts, plan_op_ids)
    fixed_op_ids = _execution_status_op_ids(facts, (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED))
    completed_op_ids = _execution_status_op_ids(facts, (EXECUTION_STATUS_COMPLETED,))
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
        prev_version=prev_version,
    )
    return facts, fixed_op_ids, completed_op_ids, execution_seed_results, all_revisions, execution_snapshot
