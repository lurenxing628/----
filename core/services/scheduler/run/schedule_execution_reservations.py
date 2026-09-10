from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.models.enums import SourceType
from core.models.operation_execution_event import EXECUTION_STATUS_PAUSED, EXECUTION_STATUS_PROCESSING
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact

from .schedule_execution_guardrails import _execution_conflict, _execution_seed_resources, _planned_duration


@dataclass(frozen=True)
class ExecutionResourceReservation:
    op_id: int
    machine_id: str
    operator_id: str
    start_time: datetime
    end_time: datetime


def build_execution_resource_reservations(
    svc: Any, *, facts: Dict[int, ExecutionFact], selected_op_ids: Set[int],
    start_dt: Optional[datetime] = None,
) -> List[ExecutionResourceReservation]:
    reservations = []
    for op_id, fact in sorted(facts.items()):
        if op_id in selected_op_ids or fact.actual_status not in (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED):
            continue
        row = svc.schedule_repo.get(int(fact.schedule_id or 0))
        op = svc.op_repo.get(op_id)
        if row is None or op is None or row.op_id != op_id or row.version != fact.schedule_version:
            raise _execution_conflict("在制工序缺少对应正式计划，本次没有写入新排程。",
                                      reason="missing_previous_schedule_row", op_id=op_id)
        if op.source != SourceType.INTERNAL.value:
            raise _execution_conflict("在制工序的资源占用类型不明确，本次没有写入新排程。",
                                      reason="invalid_execution_resource_source", op_id=op_id)
        machine_id, operator_id = _execution_seed_resources(fact, op_id=op_id)
        if svc.machine_repo.get(machine_id) is None or svc.operator_repo.get(operator_id) is None:
            raise _execution_conflict("在制工序的实际设备或人员不存在，本次没有写入新排程。",
                                      reason="unknown_actual_resource", op_id=op_id)
        if fact.actual_start_time is None:
            raise _execution_conflict("在制工序缺少实际开工时间，本次没有写入新排程。",
                                      reason="missing_actual_start_time", op_id=op_id)
        end_time = fact.actual_start_time + _planned_duration(row, svc, op_id=op_id)
        if start_dt is not None and end_time <= start_dt:
            raise _execution_conflict(
                "未选中的在制工序已超过预计结束时间，但还没有完工反馈，无法确认资源何时释放。本次没有写入新排程。",
                reason="execution_resource_release_unknown", op_id=op_id,
            )
        reservations.append(ExecutionResourceReservation(
            op_id, machine_id, operator_id, fact.actual_start_time, end_time,
        ))
    return reservations


def reserve_execution_machines(
    downtime_map: Dict[str, Any], reservations: List[ExecutionResourceReservation],
) -> Dict[str, Any]:
    result = {key: list(value) for key, value in downtime_map.items()}
    for reservation in reservations:
        result.setdefault(reservation.machine_id, []).append((reservation.start_time, reservation.end_time))
    return {key: sorted(value) for key, value in result.items()}


class ExecutionResourceCalendar:
    """Run-local personnel release floors; no writes to the work calendar.

    These are already live operations, not future pending reservations. The
    operator remains unavailable until the validated estimated release, even
    when a caller asks to backdate the new plan before the actual start.
    """

    def __init__(self, calendar: Any, reservations: List[ExecutionResourceReservation]) -> None:
        self._calendar = calendar
        self._release_by_operator: Dict[str, datetime] = {}
        for reservation in reservations:
            operator_id = reservation.operator_id
            self._release_by_operator[operator_id] = max(
                self._release_by_operator.get(operator_id, reservation.end_time), reservation.end_time,
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._calendar, name)

    def adjust_to_working_time(
        self, dt: datetime, *, priority=None, machine_id=None, operator_id=None,
    ) -> datetime:
        release = self._release_by_operator.get(str(operator_id or "").strip())
        return self._calendar.adjust_to_working_time(
            max(dt, release) if release is not None else dt,
            priority=priority, machine_id=machine_id, operator_id=operator_id,
        )
