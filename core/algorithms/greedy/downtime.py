from __future__ import annotations

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
    timeline.setdefault(resource_id, []).append((start, end))


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
    ordered = sorted([(s, e) for s, e in (segments or []) if e > s], key=lambda x: (x[0], x[1]))
    if not ordered:
        return cur

    duration = timedelta(hours=dur)
    guard = 0
    while True:
        guard += 1
        if guard > (len(ordered) + 1):
            return cur
        shift = find_overlap_shift_end(ordered, cur, cur + duration)
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
        # 防御：非法区间（空/逆序）应被忽略，避免误判重叠导致不必要的后移
        if e <= s:
            continue
        if end <= s or start >= e:
            continue
        if shift is None or e > shift:
            shift = e
    return shift

