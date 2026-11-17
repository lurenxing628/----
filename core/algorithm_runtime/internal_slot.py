from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Optional, Sequence, Tuple

from core.algorithm_contracts.material_release import released_start
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch

from .busy_block_skip import advance_busy_block
from .calendar_timing_memo import TimingCalendar
from .downtime import SegmentOverlapIndex
from .resource_quality import MachineTypeState, slot_changeover_penalty
from .slot_overlap_reuse import SlotOverlapReuse


@dataclass(frozen=True)
class InternalSlotEstimate:
    machine_id: str
    operator_id: str
    start_time: datetime
    end_time: datetime
    total_hours: float
    changeover_penalty: int
    blocked_by_window: bool = False
    abort_after_hit: bool = False
    scan_span: Optional[Tuple[datetime, datetime]] = None


def _slot_segments(
    *,
    machine_timeline: Sequence[Tuple[datetime, datetime]],
    operator_timeline: Sequence[Tuple[datetime, datetime]],
    machine_downtimes: Sequence[Tuple[datetime, datetime]],
    overlap_reuse: Optional[SlotOverlapReuse] = None,
    machine_id: str = "",
    operator_id: str = "",
) -> Tuple[SegmentOverlapIndex, SegmentOverlapIndex, SegmentOverlapIndex]:
    """把机台/人员/停机三组段集各包成重叠查询索引。

    只读契约：不再做防御性 list() 拷贝（segment_groups 全程只读、不逃逸，
    拷贝纯属浪费）；索引绝不修改输入，评估期间调用方也不得变异时间轴。
    索引惰性物化：0-hop 评估保持旧实现的单次线性扫描成本，一旦避让循环
    真的 hop，重叠查询由每组每 hop O(T) 线性重扫降为 O(log T)
    （见 SegmentOverlapIndex）。
    SGS 显式传入 overlap_reuse 时，用精确内容快照复用本趟已有索引；
    其他调用保持一次评估内复用，不扩大缓存生命周期。
    """
    if overlap_reuse is not None:
        return (
            overlap_reuse.index("machine", machine_id, machine_timeline),
            overlap_reuse.index("operator", operator_id, operator_timeline),
            overlap_reuse.index("downtime", machine_id, machine_downtimes),
        )
    return (
        SegmentOverlapIndex(machine_timeline),
        SegmentOverlapIndex(operator_timeline),
        SegmentOverlapIndex(machine_downtimes),
    )


def _max_shift_count(segment_groups: Tuple[SegmentOverlapIndex, ...]) -> int:
    return max(sum(len(index) for index in segment_groups) + 1, 10)


def _adjust_slot_start(calendar: TimingCalendar, start_time: datetime, *, priority: Any, operator_id: str) -> datetime:
    return calendar.adjust_to_working_time(start_time, priority=priority, operator_id=operator_id)


def _latest_overlap_shift_end(
    segment_groups: Tuple[SegmentOverlapIndex, ...],
    earliest: datetime,
    end_time: datetime,
) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for index in segment_groups:
        candidate = index.shift_end(earliest, end_time)
        if candidate is not None and (latest is None or candidate > latest):
            latest = candidate
    return latest


def _shifted_start(calendar: TimingCalendar, *, earliest: datetime, shift_to: datetime, priority: Any, operator_id: str) -> datetime:
    return _adjust_slot_start(calendar, max(earliest, shift_to), priority=priority, operator_id=operator_id)


def _walk(
    calendar: TimingCalendar,
    *,
    release: datetime,
    total_base: float,
    priority: Any,
    machine_id: str,
    operator_id: str,
    segment_groups: Tuple[SegmentOverlapIndex, ...],
    abort_after: Optional[datetime],
) -> Tuple[datetime, datetime, float, Optional[Tuple[datetime, datetime]], bool]:
    """(start, end, working hours, scan_span, aborted) of the first attempt from ``release`` clear of every busy segment.

    An aborted walk stops at the first start past ``abort_after``: end equals start, hours are 0 and scan_span is None.
    """
    max_shifts = _max_shift_count(segment_groups)
    earliest = _adjust_slot_start(calendar, release, priority=priority, operator_id=operator_id)
    if abort_after is not None and earliest > abort_after:
        return earliest, earliest, 0.0, None, True
    shift_count = 0
    # Busy blocks outside [scan_start, scan_end] never steered this walk; the SGS pair memo relies on that.
    scan_start = scan_end = earliest
    while True:
        end_time = calendar.add_effective_hours(earliest, total_base, priority=priority, operator_id=operator_id)
        shift_to = _latest_overlap_shift_end(segment_groups, earliest, end_time)
        if shift_to is None:
            hours = calendar.working_hours_between(earliest, end_time, priority=priority, operator_id=operator_id)
            return earliest, end_time, float(hours), (scan_start, max(scan_end, end_time)), False

        if end_time > earliest:
            shift_to = advance_busy_block(calendar, earliest=earliest, shift_to=shift_to,
                segment_groups=segment_groups, total_base=total_base, priority=priority,
                operator_id=operator_id, abort_after=abort_after)
        scan_end = max(scan_end, end_time, shift_to)

        shift_count += 1
        if shift_count > max_shifts:
            raise RuntimeError(
                f"自制工序避让超出显式上界：machine_id={machine_id!r} operator_id={operator_id!r} max_shifts={max_shifts}"
            )
        earliest = _shifted_start(calendar, earliest=earliest, shift_to=shift_to, priority=priority, operator_id=operator_id)
        if abort_after is not None and earliest > abort_after:
            return earliest, earliest, 0.0, None, True


def refresh_changeover_penalty(
    estimate: InternalSlotEstimate, *, op: OpForScheduleAlgo, machine_id: str,
    last_op_type_by_machine: Optional[MachineTypeState],
) -> InternalSlotEstimate:
    """``estimate`` with the changeover penalty a fresh scan ending at the same slot would report now."""
    penalty = slot_changeover_penalty(
        last_op_type_by_machine, op=op, machine_id=machine_id, start=estimate.start_time, end=estimate.end_time,
    )
    return estimate if penalty == estimate.changeover_penalty else replace(estimate, changeover_penalty=penalty)


def estimate_internal_slot(
    *,
    calendar: TimingCalendar,
    op: OpForScheduleAlgo,
    batch: Batch,
    machine_id: str,
    operator_id: str,
    base_time: datetime,
    prev_end: datetime,
    machine_timeline: Sequence[Tuple[datetime, datetime]],
    operator_timeline: Sequence[Tuple[datetime, datetime]],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Sequence[Tuple[datetime, datetime]],
    last_op_type_by_machine: Optional[MachineTypeState],
    abort_after: Optional[datetime],
    total_hours_base: float,
    overlap_reuse: Optional[SlotOverlapReuse] = None,
) -> InternalSlotEstimate:
    priority = batch.priority
    if total_hours_base == 0.0:
        # A zero-hour operation is a point event: no busy or downtime segment can steer it.
        segment_groups = _slot_segments(machine_timeline=(), operator_timeline=(), machine_downtimes=())
    else:
        segment_groups = _slot_segments(
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            machine_downtimes=machine_downtimes,
            overlap_reuse=overlap_reuse,
            machine_id=machine_id,
            operator_id=operator_id,
        )
    start_time, end_time, total_hours, scan_span, aborted = _walk(
        calendar, release=released_start(op, max(prev_end, base_time)), total_base=total_hours_base,
        priority=priority, machine_id=machine_id, operator_id=operator_id, segment_groups=segment_groups,
        abort_after=abort_after,
    )
    if aborted:
        return InternalSlotEstimate(
            machine_id=machine_id, operator_id=operator_id, start_time=start_time, end_time=end_time,
            total_hours=total_hours, changeover_penalty=0, abort_after_hit=True,
        )
    return InternalSlotEstimate(
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=start_time,
        end_time=end_time,
        total_hours=total_hours,
        changeover_penalty=slot_changeover_penalty(
            last_op_type_by_machine, op=op, machine_id=machine_id,
            start=start_time, end=end_time,
        ),
        blocked_by_window=bool(end_dt_exclusive is not None and end_time >= end_dt_exclusive),
        scan_span=scan_span,
    )


def estimate_point_slot(*, calendar: Any, priority: Any, machine_id: str, operator_id: str, start: datetime) -> Tuple[datetime, datetime]:
    """Where zero hours from ``start`` land on the calendar, through the same walk as every operation slot.

    A point event occupies no resource time and has no material lower bound or changeover, so only the
    calendar's shift, priority and personal rules decide; a point is valid when both instants equal ``start``.
    """
    segment_groups = _slot_segments(machine_timeline=(), operator_timeline=(), machine_downtimes=())
    start_time, end_time, _hours, _scan_span, _aborted = _walk(
        calendar, release=start, total_base=0.0, priority=priority, machine_id=machine_id,
        operator_id=operator_id, segment_groups=segment_groups, abort_after=None,
    )
    return start_time, end_time
