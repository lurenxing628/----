from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_runtime.calendar_timing_memo import (
    ACCESSOR_HOOKS,
    TIMING_METHODS,
    member_identity_guard,
    native_timing_calendar,
    register_calendar_timing_guard,
)
from core.algorithm_runtime.checkpoint_calendar import checkpoint_calendar_signature, register_checkpoint_calendar
from core.algorithm_runtime.static_attribute import static_attribute
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

    The timing surface is defined explicitly rather than borrowed through
    ``__getattr__``: static attribute reads must see the overlay's own methods so
    the per-decode timing memo, shared slots, busy-block closure and graph
    priority pruning can certify it. Its answers are pure functions of the
    arguments once the release floors are fixed, and the floors never change
    after construction; ``certified_decode_checkpoint_snapshot`` binds them.
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

    def _release(self, operator_id: Any) -> Optional[datetime]:
        return self._release_by_operator.get(str(operator_id or "").strip())

    def adjust_to_working_time(
        self, dt: datetime, *, priority=None, machine_id=None, operator_id=None,
    ) -> datetime:
        release = self._release(operator_id)
        return self._calendar.adjust_to_working_time(
            max(dt, release) if release is not None else dt,
            priority=priority, machine_id=machine_id, operator_id=operator_id,
        )

    def add_working_hours(self, start: datetime, hours: Any, priority=None, machine_id=None, operator_id=None) -> datetime:
        return self._calendar.add_working_hours(start, hours, priority=priority, machine_id=machine_id, operator_id=operator_id)

    def get_efficiency(self, dt: datetime, machine_id=None, operator_id=None) -> Any:
        return self._calendar.get_efficiency(dt, machine_id=machine_id, operator_id=operator_id)

    def certified_slot_window(self, dt: datetime, *, priority=None, operator_id=None) -> Optional[Tuple[datetime, datetime]]:
        """The underlying constant work window, only where the overlay is the identity on ``adjust``.

        Below an operator's release floor ``adjust_to_working_time`` jumps forward, so no
        constant-window proof exists there; at or after the floor the overlay answers exactly
        like the underlying calendar, whose window is clamped to start no earlier than the floor.
        """
        release = self._release(operator_id)
        if release is not None and dt < release:
            return None
        if static_attribute(self._calendar, "certified_slot_window") is None:
            return None
        window = self._calendar.certified_slot_window(dt, priority=priority, operator_id=operator_id)
        if window is None or release is None:
            return window
        return max(window[0], release), window[1]

    def certified_decode_checkpoint_snapshot(self):
        return "execution-release-v1", checkpoint_calendar_signature(self._calendar), tuple(sorted(self._release_by_operator.items()))


_OVERLAY_GUARDED_MEMBERS = TIMING_METHODS + ACCESSOR_HOOKS + ("__dict__", "_release")
_OVERLAY_CLASS_UNCHANGED = member_identity_guard(ExecutionResourceCalendar, _OVERLAY_GUARDED_MEMBERS)


def _native_release_floors(releases: Any) -> bool:
    if type(releases) is not dict:
        return False
    return all(type(key) is str and type(value) is datetime and value.tzinfo is None for key, value in releases.items())


def native_execution_overlay_timing(overlay: Any) -> bool:
    """The overlay's own timing methods are intact and the calendar underneath is itself certified."""
    if type(overlay) is not ExecutionResourceCalendar or not _OVERLAY_CLASS_UNCHANGED():
        return False
    fields = vars(overlay)
    if not fields.keys().isdisjoint(_OVERLAY_GUARDED_MEMBERS):
        return False
    if not _native_release_floors(fields.get("_release_by_operator")):
        return False
    return native_timing_calendar(fields.get("_calendar"))


register_checkpoint_calendar(ExecutionResourceCalendar, ExecutionResourceCalendar.certified_decode_checkpoint_snapshot)
register_calendar_timing_guard(ExecutionResourceCalendar, native_execution_overlay_timing)
