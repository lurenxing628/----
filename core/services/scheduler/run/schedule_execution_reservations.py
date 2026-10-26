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
    *, facts: Dict[int, ExecutionFact], selected_op_ids: Set[int], start_dt: datetime, capture,
) -> List[ExecutionResourceReservation]:
    reservations = []
    for op_id, fact in sorted(facts.items()):
        if op_id in selected_op_ids or fact.actual_status not in (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED):
            continue
        saved = capture.index("Schedule", "id").get(fact.schedule_id)
        raw = capture.index("BatchOperations", "id").get(op_id)
        if saved is None or raw is None or saved["op_id"] != op_id or saved["version"] != fact.schedule_version:
            raise _execution_conflict("在制工序缺少对应正式计划，本次没有写入新排程。",
                                      reason="missing_previous_schedule_row", op_id=op_id)
        if raw["source"] == SourceType.EXTERNAL.value:
            if fact.actual_machine_id is not None or fact.actual_operator_id is not None:
                raise _execution_conflict("外协报工不能占用本厂设备或人员，请核对实际资源记录。",
                                          reason="external_actual_resource_conflict", op_id=op_id)
            # Supplier work keeps its execution identity, but reserves no
            # factory machine or operator while this run schedules other work.
            continue
        if raw["source"] != SourceType.INTERNAL.value:
            raise _execution_conflict("在制工序的资源占用类型不明确，本次没有写入新排程。",
                                      reason="invalid_execution_resource_source", op_id=op_id)
        machine_id, operator_id = _execution_seed_resources(fact, op_id=op_id)
        if (machine_id not in capture.index("Machines", "machine_id")
                or operator_id not in capture.index("Operators", "operator_id")):
            raise _execution_conflict("在制工序的实际设备或人员不存在，本次没有写入新排程。",
                                      reason="unknown_actual_resource", op_id=op_id)
        if fact.actual_start_time is None:
            raise _execution_conflict("在制工序缺少实际开工时间，本次没有写入新排程。",
                                      reason="missing_actual_start_time", op_id=op_id)
        end_time = fact.actual_start_time + _planned_duration(saved, op_id=op_id)
        if end_time <= start_dt:
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
    if not reservations:
        return downtime_map
    result = dict(downtime_map)
    added: Dict[str, List[Tuple[datetime, datetime]]] = {}
    for reservation in reservations:
        added.setdefault(reservation.machine_id, []).append((reservation.start_time, reservation.end_time))
    for machine_id, spans in added.items():
        result[machine_id] = sorted([*result.get(machine_id, ()), *spans])
    return result


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

    def adjust_to_working_time(self, dt: datetime, *, priority=None, operator_id: Any = None) -> datetime:
        # 与 __init__ 写入同一口径，按人员编号原值查找。
        release = self._release_by_operator.get(operator_id)
        return self._calendar.adjust_to_working_time(
            max(dt, release) if release is not None else dt, priority=priority, operator_id=operator_id,
        )

    def add_working_hours(self, start: datetime, hours: Any, priority=None, operator_id=None) -> datetime:
        return self._calendar.add_working_hours(start, hours, priority=priority, operator_id=operator_id)

    def add_effective_hours(self, start: datetime, hours: Any, priority=None, operator_id=None) -> datetime:
        return self._calendar.add_effective_hours(start, hours, priority=priority, operator_id=operator_id)

    def add_calendar_days(self, start: datetime, days: Any) -> datetime:
        return self._calendar.add_calendar_days(start, days)

    def get_efficiency(self, dt: datetime, operator_id=None) -> Any:
        return self._calendar.get_efficiency(dt, operator_id=operator_id)

    def certified_slot_window(self, dt: datetime, *, priority=None, operator_id: Any = None) -> Optional[Tuple[datetime, datetime]]:
        """The underlying constant work window, only where the overlay is the identity on ``adjust``.

        Below an operator's release floor ``adjust_to_working_time`` jumps forward, so no
        constant-window proof exists there; at or after the floor the overlay answers exactly
        like the underlying calendar, whose window is clamped to start no earlier than the floor.
        """
        release = self._release_by_operator.get(operator_id)
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


_OVERLAY_GUARDED_MEMBERS = TIMING_METHODS + ACCESSOR_HOOKS + ("__dict__",)
_OVERLAY_CLASS_UNCHANGED = member_identity_guard(ExecutionResourceCalendar, _OVERLAY_GUARDED_MEMBERS)
_OVERLAY_CALENDAR_DAYS_UNCHANGED = member_identity_guard(ExecutionResourceCalendar, ("add_calendar_days",))


def native_execution_overlay_timing(overlay: Any) -> bool:
    """The overlay's own timing methods are intact and the calendar underneath is itself certified."""
    if type(overlay) is not ExecutionResourceCalendar or not _OVERLAY_CLASS_UNCHANGED():
        return False
    fields = vars(overlay)
    if not fields.keys().isdisjoint(_OVERLAY_GUARDED_MEMBERS):
        return False
    return native_timing_calendar(fields.get("_calendar"))


def _native_execution_calendar_days(overlay: Any) -> bool:
    if not _OVERLAY_CALENDAR_DAYS_UNCHANGED() or "add_calendar_days" in vars(overlay):
        return False
    return native_timing_calendar(overlay._calendar, include_calendar_days=True)


register_checkpoint_calendar(ExecutionResourceCalendar, ExecutionResourceCalendar.certified_decode_checkpoint_snapshot)
register_calendar_timing_guard(ExecutionResourceCalendar, native_execution_overlay_timing,
                               calendar_days_guard=_native_execution_calendar_days)
