from __future__ import annotations

import bisect
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


def get_resource_available(
    timeline: Dict[str, List[Tuple[datetime, datetime]]],
    resource_id: str,
    base_time: datetime,
) -> datetime:
    if not resource_id:
        return base_time
    segments = timeline.get(resource_id) or []
    if not segments:
        return base_time
    return max(end for _, end in segments)


def occupy_resource(
    timeline: Dict[str, List[Tuple[datetime, datetime]]],
    resource_id: str,
    start: datetime,
    end: datetime,
) -> None:
    if not resource_id:
        return
    segments = timeline.setdefault(resource_id, [])
    bisect.insort(segments, (start, end))


def find_earliest_available_start(
    segments: List[Tuple[datetime, datetime]],
    base_time: datetime,
    duration_hours: float,
) -> datetime:
    try:
        dur = float(duration_hours)
    except Exception:
        dur = 0.0
    if dur <= 0:
        return base_time

    cur = base_time
    valid_segments = [(s, e) for s, e in (segments or []) if e > s]
    if not valid_segments:
        return cur

    duration = timedelta(hours=dur)
    guard = 0
    while True:
        guard += 1
        if guard > (len(valid_segments) + 1):
            return cur
        shift = find_overlap_shift_end(valid_segments, cur, cur + duration)
        if shift is None or shift <= cur:
            return cur
        cur = shift


def find_overlap_shift_end(
    segments: List[Tuple[datetime, datetime]],
    start: datetime,
    end: datetime,
) -> Optional[datetime]:
    """
    若 [start, end) 与 segments 中任意区间重叠，返回“需要推迟到的最晚结束时刻”（max end）。
    """
    shift: Optional[datetime] = None
    for s, e in segments or []:
        if e <= s:
            continue
        if s >= end:
            break
        if end <= s or start >= e:
            continue
        if shift is None or e > shift:
            shift = e
    return shift
