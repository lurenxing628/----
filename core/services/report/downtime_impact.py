from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .calculation_helpers import is_internal_source, overlap_seconds, parse_dt

DowntimeSegment = Tuple[datetime, datetime, str, str]
ScheduleSegment = Tuple[datetime, datetime]


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
) -> List[Dict[str, Any]]:
    by_machine_dt, machine_name = _index_downtime_rows(downtime_rows)
    by_machine_sch = _index_schedule_rows(schedule_rows)

    items = [
        _build_downtime_impact_row(mc, dts, machine_name.get(mc), by_machine_sch.get(mc) or [], start_dt, end_dt_excl)
        for mc, dts in by_machine_dt.items()
    ]
    items.sort(key=lambda x: (-(x.get("downtime_hours") or 0.0), x.get("machine_id") or ""))
    return items


def _index_downtime_rows(
    downtime_rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, List[DowntimeSegment]], Dict[str, Any]]:
    by_machine_dt: Dict[str, List[DowntimeSegment]] = {}
    machine_name: Dict[str, Any] = {}
    for r in downtime_rows:
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt:
            continue
        by_machine_dt.setdefault(mc, []).append((s_dt, e_dt, str(r.get("reason_code") or ""), str(r.get("reason_detail") or "")))
        if mc not in machine_name:
            machine_name[mc] = r.get("machine_name")
    return by_machine_dt, machine_name


def _index_schedule_rows(schedule_rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[ScheduleSegment]]:
    by_machine_sch: Dict[str, List[ScheduleSegment]] = {}
    for r in schedule_rows:
        if not is_internal_source(r.get("source")):
            continue
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt:
            continue
        by_machine_sch.setdefault(mc, []).append((s_dt, e_dt))
    return by_machine_sch


def _downtime_seconds(downtime_segments: Sequence[DowntimeSegment], start_dt: datetime, end_dt_excl: datetime) -> float:
    return sum(overlap_seconds(ds, de, start_dt, end_dt_excl) for ds, de, _, _ in downtime_segments)


def _schedule_overlap(downtime_segments: Sequence[DowntimeSegment], schedule_segments: Sequence[ScheduleSegment]) -> Tuple[float, int]:
    overlap_sec = 0.0
    impact_count = 0
    for ds, de, _, _ in downtime_segments:
        for ss, se in schedule_segments:
            sec = overlap_seconds(ds, de, ss, se)
            if sec > 0:
                overlap_sec += sec
                impact_count += 1
    return overlap_sec, impact_count


def _build_downtime_impact_row(
    machine_id: str,
    downtime_segments: Sequence[DowntimeSegment],
    machine_name: Any,
    schedule_segments: Sequence[ScheduleSegment],
    start_dt: datetime,
    end_dt_excl: datetime,
) -> Dict[str, Any]:
    downtime_sec = _downtime_seconds(downtime_segments, start_dt, end_dt_excl)
    overlap_sec, impact_count = _schedule_overlap(downtime_segments, schedule_segments)
    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "downtime_hours": round(downtime_sec / 3600.0, 2),
        "downtime_count": len(downtime_segments),
        "schedule_overlap_hours": round(overlap_sec / 3600.0, 2),
        "schedule_overlap_count": int(impact_count),
    }
