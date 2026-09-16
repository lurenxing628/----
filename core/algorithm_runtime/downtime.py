from __future__ import annotations

import bisect
import math
import operator
from datetime import datetime, timedelta
from itertools import accumulate, islice
from typing import Dict, List, Optional, Sequence, Tuple

from .sgs_estimate_reuse import current_sgs_handoff


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
    handoff = current_sgs_handoff()
    if handoff is not None:
        # The SGS pair memo proves memoized estimates current against exactly the segments added since.
        handoff.observe_occupation(timeline, resource_id, start, end)


class SegmentOverlapIndex:
    """有序段集上的重复重叠查询索引（避让循环专用）。

    查询语义与对同一段集调用 find_overlap_shift_end 逐一一致：与 [start, end)
    重叠的段全部落在“起点 < end”的前缀里，该前缀内最大的结束时刻若大于
    start，就是需要避让到的时刻。

    物化是惰性的：首次 shift_end 直接在原序列上做一次旧式线性扫描（避让循环
    最常见的 0-hop 评估保持旧实现的单次扫描成本，且不再做防御性拷贝）；第二
    次查询前才构建“起点数组 + 前缀最大结束时刻数组”，此后每次查询只需一次
    bisect，把每 hop 的 O(n) 线性重扫降为 O(log n)。

    契约：
    - segments 必须按起点升序（占用时间轴由 occupy_resource 的 bisect.insort
      维护，停机表由调度入口 _normalize_machine_downtimes 排序）。乱序输入
      在物化时抛 ValueError，不做静默排序回退；首查线性扫描与旧实现同语义，
      故 0-hop 场景对乱序输入的行为与旧实现一致。
    - 段之间允许互相重叠或嵌套（停机表只排序、不合并），查询结果仍精确。
    - 只读：本索引绝不修改输入；构建后持有输入序列引用，查询期间调用方
      不得变异该序列。
    - len() 返回原始段数（含无效段），与旧 _max_shift_count 的口径一致。
    """

    __slots__ = ("_segments", "_starts", "_prefix_max_ends", "_scanned_once", "_covered_starts", "_covered_ends", "_append_native", "_coverage_native")

    def __init__(self, segments: Optional[Sequence[Tuple[datetime, datetime]]]) -> None:
        self._segments = segments or ()
        self._starts: Optional[Sequence[datetime]] = None
        self._prefix_max_ends: Sequence[datetime] = ()
        self._scanned_once = False
        self._covered_starts: Optional[Sequence[datetime]] = None
        self._covered_ends: Sequence[datetime] = ()
        self._append_native: Optional[bool] = None if type(segments) is tuple else False
        self._coverage_native: Optional[bool] = None

    def __len__(self) -> int:
        return len(self._segments)

    def begin_estimate(self) -> None:
        # Reuse materialized arrays, but retain the first linear query of each
        # estimate when still lazy (including the existing unsorted 0-hop contract).
        self._scanned_once = False

    def shift_end(self, start: datetime, end: datetime) -> Optional[datetime]:
        """等价于 find_overlap_shift_end(同一段集, start, end)。"""
        if self._starts is None:
            if not self._scanned_once:
                self._scanned_once = True
                return find_overlap_shift_end(self._segments, start, end)
            starts = self._materialize()
        else:
            starts = self._starts
        hi = bisect.bisect_left(starts, end)
        if hi == 0:
            return None
        max_end = self._prefix_max_ends[hi - 1]
        return max_end if max_end > start else None

    def _materialize(self) -> Sequence[datetime]:
        # 位于 SGS 逐候选评分最内层，构建走 C 层批量操作（zip/map/accumulate），
        # 不逐元素跑 Python 循环。
        segs = self._segments
        if segs:
            starts, ends = zip(*segs)
        else:
            starts, ends = (), ()
        if any(map(operator.ge, starts, ends)):
            starts, ends = _drop_invalid_segments(starts, ends)
        if any(map(operator.gt, starts, islice(starts, 1, None))):
            raise ValueError(_unsorted_segments_message(starts))
        self._starts = starts
        self._prefix_max_ends = tuple(accumulate(ends, max))
        return starts

    def with_appended_segment(
        self, snapshot: Tuple[Tuple[datetime, datetime], ...],
    ) -> Optional[SegmentOverlapIndex]:
        """Derive a new immutable index only from a verified sorted native append."""
        if not self._can_append_snapshot(snapshot):
            return None
        start, end = snapshot[-1]
        derived = SegmentOverlapIndex(snapshot)
        derived._starts = self._starts
        derived._prefix_max_ends = self._prefix_max_ends
        derived._covered_starts = self._covered_starts
        derived._covered_ends = self._covered_ends
        derived._append_native = True
        derived._coverage_native = True
        if end > start:
            derived._starts = tuple(self._starts or ()) + (start,)
            previous_end = self._prefix_max_ends[-1] if self._prefix_max_ends else end
            derived._prefix_max_ends = tuple(self._prefix_max_ends) + (max(previous_end, end),)
            derived._append_covered_segment(start, end)
        return derived

    def _can_append_snapshot(self, snapshot: Tuple[Tuple[datetime, datetime], ...]) -> bool:
        if (self._starts is None or type(snapshot) is not tuple
                or len(snapshot) != len(self._segments) + 1 or not _plain_segment(snapshot[-1])):
            return False
        if self._append_native is None:
            self._append_native = all(_plain_segment(segment) for segment in self._segments)
        if not self._append_native:
            return False
        if not all(map(operator.is_, snapshot, self._segments)):
            prefix = snapshot[:-1]
            if not all(_plain_segment(segment) for segment in prefix) or prefix != self._segments:
                return False
        start, end = snapshot[-1]
        return end <= start or not self._starts or start >= self._starts[-1]

    def _append_covered_segment(self, start: datetime, end: datetime) -> None:
        if self._covered_starts is None:
            return
        if self._covered_ends and start <= self._covered_ends[-1]:
            if end > self._covered_ends[-1]:
                self._covered_ends = tuple(self._covered_ends[:-1]) + (end,)
        else:
            self._covered_starts = tuple(self._covered_starts) + (start,)
            self._covered_ends = tuple(self._covered_ends) + (end,)

    def covered_end(self, instant: datetime) -> Optional[datetime]:
        """End of the continuous occupied block containing this instant.

        This is intentionally separate from shift_end's exact one-hop contract.
        Touching positive intervals cover their common boundary without a gap.
        """
        if self._covered_starts is None:
            if self._starts is None:
                self._materialize()
            merged: List[Tuple[datetime, datetime]] = []
            for start, end in self._segments:
                if end <= start:
                    continue
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            self._covered_starts = tuple(row[0] for row in merged)
            self._covered_ends = tuple(row[1] for row in merged)
        index = bisect.bisect_right(self._covered_starts, instant) - 1
        if index >= 0 and instant < self._covered_ends[index]:
            return self._covered_ends[index]
        return None

    def has_native_coverage(self) -> bool:
        """Certify callback-free coverage under this index's immutable-input contract.

        Only called after the ordinary first coverage query. Custom containers or
        datetime subclasses retain the original one-step behavior. Reused SGS
        indexes own tuple snapshots; changed timelines create a different index.
        """
        if self._coverage_native is None:
            self._coverage_native = type(self._segments) in (tuple, list) and all(
                _plain_segment(segment) for segment in self._segments
            )
        return self._coverage_native


def _plain_segment(segment: Tuple[datetime, datetime]) -> bool:
    return (type(segment) is tuple and len(segment) == 2
            and all(type(value) is datetime and value.tzinfo is None for value in segment))


def _drop_invalid_segments(
    starts: Sequence[datetime],
    ends: Sequence[datetime],
) -> Tuple[Tuple[datetime, ...], Tuple[datetime, ...]]:
    """过滤无效段（end <= start），与旧 find_overlap_shift_end 的逐段跳过语义一致。"""
    kept = [(s, e) for s, e in zip(starts, ends) if e > s]
    if not kept:
        return (), ()
    new_starts, new_ends = zip(*kept)
    return new_starts, new_ends


def _unsorted_segments_message(starts: Sequence[datetime]) -> str:
    for prev, cur in zip(starts, islice(starts, 1, None)):
        if cur < prev:
            return f"重叠索引要求段按起点升序：{cur!r} 出现在 {prev!r} 之后"
    return "重叠索引要求段按起点升序"


def find_earliest_available_start(
    segments: List[Tuple[datetime, datetime]],
    base_time: datetime,
    duration_hours: float,
) -> datetime:
    """segments 必须按起点升序（乱序输入在避让进入第二次查询时抛 ValueError，见 SegmentOverlapIndex）。"""
    try:
        dur = float(duration_hours)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"排产时长必须是数字：{duration_hours!r}") from exc
    if not math.isfinite(dur):
        raise ValueError(f"排产时长必须是有限数字：{duration_hours!r}")
    if dur <= 0:
        return base_time

    cur = base_time
    index = SegmentOverlapIndex(segments)
    if not len(index):
        return cur

    duration = timedelta(hours=dur)
    guard = 0
    while True:
        guard += 1
        if guard > (len(index) + 1):
            return cur
        shift = index.shift_end(cur, cur + duration)
        if shift is None or shift <= cur:
            return cur
        cur = shift


def find_overlap_shift_end(
    segments: Sequence[Tuple[datetime, datetime]],
    start: datetime,
    end: datetime,
) -> Optional[datetime]:
    """
    若 [start, end) 与 segments 中任意区间重叠，返回“需要推迟到的最晚结束时刻”（max end）。

    segments 需按起点升序（提前 break 依赖有序）。一次性查询用本函数即可；
    对同一段集反复查询的避让循环应改用 SegmentOverlapIndex，避免每次从头线性重扫。
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
