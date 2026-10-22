from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.services.capacity.plan_calendar_intervals import IntervalIndex
from core.shared.degradation import DegradationCollector
from core.shared.local_datetime import parse_local_datetime as parse_dt

from .calculation_helpers import is_internal_source, is_valid_interval, overlap_seconds
from .report_degradation import (
    record_report_bad_time_row,
    record_report_downtime_overlap_merged,
    record_report_missing_machine_row,
)

DowntimeSegment = Tuple[datetime, datetime]
ScheduleSegment = Tuple[datetime, datetime]
TimeInterval = Tuple[datetime, datetime]


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
    degradation_collector: Optional[DegradationCollector] = None,
) -> List[Dict[str, Any]]:
    by_machine_dt, machine_name = _index_downtime_rows(downtime_rows, degradation_collector=degradation_collector)
    by_machine_sch = _index_schedule_rows(schedule_rows, degradation_collector=degradation_collector)

    items = []
    for mc, dts in by_machine_dt.items():
        merged_intervals = _merge_downtime_intervals(mc, dts, degradation_collector=degradation_collector)
        items.append(
            _build_downtime_impact_row(
                mc, dts, merged_intervals, machine_name.get(mc), by_machine_sch.get(mc) or [], start_dt, end_dt_excl
            )
        )
    items.sort(key=lambda x: (-(x.get("downtime_hours") or 0.0), x.get("machine_id") or ""))
    return items


def _index_downtime_rows(
    downtime_rows: List[Dict[str, Any]],
    *,
    degradation_collector: Optional[DegradationCollector] = None,
) -> Tuple[Dict[str, List[DowntimeSegment]], Dict[str, Any]]:
    by_machine_dt: Dict[str, List[DowntimeSegment]] = {}
    machine_name: Dict[str, Any] = {}
    for r in downtime_rows:
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            # 空设备编号只能来自库外直写；与坏时间行同契约，丢弃必须降级留痕，不许静默少算停机工时。
            record_report_missing_machine_row(degradation_collector, scope="report.downtime.downtime", row=r)
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt or not is_valid_interval(s_dt, e_dt):
            record_report_bad_time_row(degradation_collector, scope="report.downtime.downtime", row=r)
            continue
        by_machine_dt.setdefault(mc, []).append((s_dt, e_dt))
        if mc not in machine_name:
            machine_name[mc] = r.get("machine_name")
    return by_machine_dt, machine_name


def _index_schedule_rows(
    schedule_rows: Sequence[Mapping[str, Any]],
    *,
    degradation_collector: Optional[DegradationCollector] = None,
) -> Dict[str, List[ScheduleSegment]]:
    by_machine_sch: Dict[str, List[ScheduleSegment]] = {}
    for r in schedule_rows:
        if not is_internal_source(r.get("source")):
            continue
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt or not is_valid_interval(s_dt, e_dt):
            record_report_bad_time_row(degradation_collector, scope="report.downtime.schedule", row=r)
            continue
        by_machine_sch.setdefault(mc, []).append((s_dt, e_dt))
    return by_machine_sch


def _merge_downtime_intervals(
    machine_id: str,
    downtime_segments: Sequence[DowntimeSegment],
    *,
    degradation_collector: Optional[DegradationCollector] = None,
) -> List[TimeInterval]:
    """同机停机段按标准区间归并后再计时。

    不归并时，同机重叠 active 行（并发查后插竞态或库外直写产生）会把重叠跨度算两遍，
    downtime_hours 可超报表窗口总长。归并只改时间口径，downtime_count 仍按原始记录数计；
    检测到重叠必须降级留痕（与同文件缺 machine_id / 坏时间行同契约），不许静默修数。
    首尾相接（前段 end == 后段 start）不算重叠，不留痕。
    """
    ordered = sorted(downtime_segments)
    merged: List[TimeInterval] = []
    for s, e in ordered:
        if merged and s < merged[-1][1]:
            prev_s, prev_e = merged[-1]
            record_report_downtime_overlap_merged(
                degradation_collector,
                scope="report.downtime.downtime",
                machine_id=machine_id,
                kept=(prev_s, prev_e),
                merged_in=(s, e),
            )
            merged[-1] = (prev_s, max(prev_e, e))
        else:
            merged.append((s, e))
    return merged


def _downtime_seconds(downtime_intervals: Sequence[TimeInterval], start_dt: datetime, end_dt_excl: datetime) -> float:
    return sum(overlap_seconds(ds, de, start_dt, end_dt_excl) for ds, de in downtime_intervals)


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
    # 工时/受影响任务按归并后的区间算（防重叠双计）；downtime_count 仍是原始记录数。
    downtime_sec = _downtime_seconds(merged_intervals, start_dt, end_dt_excl)
    overlap_sec, impact_count = _schedule_overlap(merged_intervals, schedule_segments)
    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "downtime_hours": round(downtime_sec / 3600.0, 2),
        "downtime_count": len(downtime_segments),
        "schedule_overlap_hours": round(overlap_sec / 3600.0, 2),
        "schedule_overlap_count": int(impact_count),
    }
