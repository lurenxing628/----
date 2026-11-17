from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from core.services.capacity.plan_calendar_intervals import IntervalIndex
from core.shared.local_datetime import row_interval

from .calculation_helpers import is_internal_source, overlap_seconds

DowntimeSegment = Tuple[datetime, datetime]
ScheduleSegment = Tuple[datetime, datetime]
TimeInterval = Tuple[datetime, datetime]


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
) -> List[Dict[str, Any]]:
    by_machine_dt, machine_name = _index_downtime_rows(downtime_rows)
    by_machine_sch = _index_schedule_rows(schedule_rows)

    items = []
    for mc, dts in by_machine_dt.items():
        merged_intervals = _merge_downtime_intervals(dts)
        items.append(
            _build_downtime_impact_row(
                mc, dts, merged_intervals, machine_name[mc], by_machine_sch.get(mc, ()), start_dt, end_dt_excl
            )
        )
    items.sort(key=lambda x: (-x["downtime_hours"], x["machine_id"]))
    return items


def _index_downtime_rows(
    downtime_rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, List[DowntimeSegment]], Dict[str, Any]]:
    """停机的设备号是 NOT NULL 外键，起止只读已保存的微秒。"""
    by_machine_dt: Dict[str, List[DowntimeSegment]] = {}
    machine_name: Dict[str, Any] = {}
    for r in downtime_rows:
        mc = r["machine_id"]
        by_machine_dt.setdefault(mc, []).append(row_interval(r))
        if mc not in machine_name:
            machine_name[mc] = r["machine_name"]
    return by_machine_dt, machine_name


def _index_schedule_rows(schedule_rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[ScheduleSegment]]:
    """本厂工序按设备分组；点事件不占设备时长，起止只读已保存的微秒。"""
    by_machine_sch: Dict[str, List[ScheduleSegment]] = {}
    for r in schedule_rows:
        mc = r["machine_id"]
        if not is_internal_source(r["source"]) or mc is None or r["is_point_event"]:
            continue
        by_machine_sch.setdefault(mc, []).append(row_interval(r))
    return by_machine_sch


def _merge_downtime_intervals(
    downtime_segments: Sequence[DowntimeSegment],
) -> List[TimeInterval]:
    """同机停机段按标准区间归并后再计时。

    不归并时，同机重叠 active 行（并发查后插竞态或库外直写产生）会把重叠跨度算两遍，
    downtime_hours 可超报表窗口总长。归并只改时间口径，downtime_count 仍按原始记录数计。
    """
    ordered = sorted(downtime_segments)
    merged: List[TimeInterval] = []
    for s, e in ordered:
        if merged and s < merged[-1][1]:
            prev_s, prev_e = merged[-1]
            merged[-1] = (prev_s, max(prev_e, e))
        else:
            merged.append((s, e))
    return merged


def _schedule_overlap(downtime_intervals: Sequence[TimeInterval], schedule_segments: Sequence[ScheduleSegment]) -> Tuple[float, int]:
    if not downtime_intervals or not schedule_segments:
        return 0.0, 0
    if len(downtime_intervals) == 1:
        # One window already needs only one pass; an index adds no useful work.
        start, end = downtime_intervals[0]
        overlap_sec, impact_count = 0.0, 0
        for low, high in schedule_segments:
            seconds = overlap_seconds(start, end, low, high)
            if seconds > 0:
                overlap_sec += seconds
                impact_count += 1
        return overlap_sec, impact_count
    downtime_index = IntervalIndex.from_normalized(downtime_intervals)
    overlap_sec = 0.0
    impact_count = 0
    for start, end in schedule_segments:
        seconds, count = downtime_index.seconds_and_count_between(start, end)
        overlap_sec += seconds
        impact_count += count
    return overlap_sec, impact_count


def _build_downtime_impact_row(
    machine_id: str,
    downtime_segments: Sequence[DowntimeSegment],
    merged_intervals: Sequence[TimeInterval],
    machine_name: Any,
    schedule_segments: Sequence[ScheduleSegment],
    start_dt: datetime,
    end_dt_excl: datetime,
) -> Dict[str, Any]:
    # 工时/受影响任务按归并并裁剪到查询窗口后的区间算（防重叠双计与窗口外计入）；downtime_count 仍是原始记录数。
    window_intervals = [
        (max(ds, start_dt), min(de, end_dt_excl))
        for ds, de in merged_intervals
        if max(ds, start_dt) < min(de, end_dt_excl)
    ]
    downtime_sec = sum((de - ds).total_seconds() for ds, de in window_intervals)
    overlap_sec, impact_count = _schedule_overlap(window_intervals, schedule_segments)
    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "downtime_hours": round(downtime_sec / 3600.0, 2),
        "downtime_count": len(downtime_segments),
        "schedule_overlap_hours": round(overlap_sec / 3600.0, 2),
        "schedule_overlap_count": impact_count,
    }
