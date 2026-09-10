"""合同测试：SegmentOverlapIndex 避让查询与旧线性扫描逐一等价（A03）。

锁四条合同：
1. 随机段集（含互相重叠/嵌套/无效空段/逆序段）+ 随机查询（含退化 end<=start 查询）下，
   同一 SegmentOverlapIndex 实例连续多次 shift_end（覆盖首查线性扫描路径与物化后
   bisect 路径）与内嵌的旧 find_overlap_shift_end 实现（oracle）以及现行一次性
   find_overlap_shift_end 三方逐一一致；
2. find_earliest_available_start 新实现与内嵌旧实现（oracle）在随机段集+随机时长下逐一一致；
3. 乱序段集 fail-loud：SegmentOverlapIndex / find_earliest_available_start /
   estimate_internal_slot 在避让真正 hop（索引物化）时对起点乱序的段集抛 ValueError，
   不静默给出顺序相关的错误避让；首查（0-hop）保持与旧实现相同的线性扫描语义；
4. 只读（A10 摘除防御性拷贝后的替代保障）：estimate_internal_slot 全程不改写
   入参时间轴/停机表。
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import List, Optional, Tuple

import pytest

from core.algorithm_runtime.downtime import (
    SegmentOverlapIndex,
    find_earliest_available_start,
    find_overlap_shift_end,
)
from core.algorithm_runtime.internal_slot import estimate_internal_slot

_BASE = datetime(2026, 1, 1, 0, 0, 0)


def _dt(hours: float) -> datetime:
    return _BASE + timedelta(hours=hours)


def _oracle_find_overlap_shift_end(
    segments: List[Tuple[datetime, datetime]],
    start: datetime,
    end: datetime,
) -> Optional[datetime]:
    """旧 find_overlap_shift_end 实现原样内嵌（等价性 oracle）。"""
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


def _oracle_find_earliest_available_start(
    segments: List[Tuple[datetime, datetime]],
    base_time: datetime,
    duration_hours: float,
) -> datetime:
    """旧 find_earliest_available_start 实现原样内嵌（等价性 oracle）。"""
    dur = float(duration_hours)
    if not math.isfinite(dur):
        raise ValueError(f"排产时长必须是有限数字：{duration_hours!r}")
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
        shift = _oracle_find_overlap_shift_end(valid_segments, cur, cur + duration)
        if shift is None or shift <= cur:
            return cur
        cur = shift


def _random_sorted_segments(rng: random.Random) -> List[Tuple[datetime, datetime]]:
    """整点小时网格上的随机段集：强制排序，故意混入重叠/嵌套/空段/逆序段。"""
    count = rng.randint(0, 40)
    segments = []
    for _ in range(count):
        start_h = rng.randint(0, 30)
        length_h = rng.randint(-2, 8)  # 负/零长度制造无效段
        segments.append((_dt(start_h), _dt(start_h + length_h)))
    segments.sort(key=lambda seg: (seg[0], seg[1]))
    return segments


class _IdentityCalendar:
    def adjust_to_working_time(self, dt, priority=None, operator_id=None):
        return dt

    def add_working_hours(self, dt, hours, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt, operator_id=None):
        return 1.0


def _entities(setup_hours: float = 0.5):
    op = SimpleNamespace(setup_hours=setup_hours, unit_hours=0.0, op_type_name="车削")
    batch = SimpleNamespace(quantity=1, priority="normal")
    return op, batch


def test_shift_end_matches_legacy_scan_on_random_segments():
    rng = random.Random(20260720)
    for _ in range(300):
        segments = _random_sorted_segments(rng)
        index = SegmentOverlapIndex(segments)
        for _ in range(20):
            q_start = _dt(rng.randint(-2, 42))
            q_end = _dt(rng.randint(-2, 42))  # 含 end<=start 的退化查询
            expected = _oracle_find_overlap_shift_end(segments, q_start, q_end)
            assert index.shift_end(q_start, q_end) == expected, (segments, q_start, q_end)
            assert find_overlap_shift_end(segments, q_start, q_end) == expected, (segments, q_start, q_end)


def test_find_earliest_available_start_matches_legacy_on_random_segments():
    rng = random.Random(20260721)
    for _ in range(300):
        segments = _random_sorted_segments(rng)
        base_time = _dt(rng.randint(-2, 35))
        duration_hours = rng.choice([0.0, 0.5, 1.0, 2.5, 7.0])
        expected = _oracle_find_earliest_available_start(segments, base_time, duration_hours)
        assert find_earliest_available_start(segments, base_time, duration_hours) == expected, (
            segments,
            base_time,
            duration_hours,
        )


def test_unsorted_segments_fail_loud_on_materialize():
    """乱序段集在避让真正 hop（第二次查询触发物化）时抛 ValueError。"""
    unsorted = [(_dt(2), _dt(3)), (_dt(0), _dt(1))]

    index = SegmentOverlapIndex(unsorted)
    # 首查走旧式线性扫描：与旧实现同语义，不因乱序抛错
    assert index.shift_end(_dt(2), _dt(2.5)) == _oracle_find_overlap_shift_end(unsorted, _dt(2), _dt(2.5)) == _dt(3)
    with pytest.raises(ValueError):
        index.shift_end(_dt(3), _dt(3.5))

    # find_earliest_available_start：首查命中 (2,3) 段触发 hop，第二次查询物化时抛错
    with pytest.raises(ValueError):
        find_earliest_available_start(unsorted, _dt(2), 0.5)

    # estimate_internal_slot：同款乱序时间轴，首 hop 后物化时抛错
    op, batch = _entities()
    with pytest.raises(ValueError):
        estimate_internal_slot(
            calendar=_IdentityCalendar(),
            op=op,
            batch=batch,
            machine_id="M1",
            operator_id="O1",
            base_time=_dt(2),
            prev_end=_dt(2),
            machine_timeline=unsorted,
            operator_timeline=[],
            end_dt_exclusive=None,
            machine_downtimes=[],
            last_op_type_by_machine=None,
            abort_after=None,
        )


def test_unsorted_invalid_segments_do_not_fail():
    """无效段（end<=start）旧实现整段忽略，乱序的无效段不应触发排序 fail-loud。"""
    segments = [(_dt(1), _dt(2)), (_dt(0), _dt(0)), (_dt(3), _dt(5))]
    index = SegmentOverlapIndex(segments)
    expected = _oracle_find_overlap_shift_end(segments, _dt(0), _dt(4))
    assert expected == _dt(5)
    # 连续查两次：首查线性路径 + 物化后 bisect 路径都不因乱序无效段抛错
    assert index.shift_end(_dt(0), _dt(4)) == expected
    assert index.shift_end(_dt(0), _dt(4)) == expected


def test_estimate_internal_slot_keeps_inputs_untouched_with_dense_timeline():
    """A10 摘除防御性拷贝后，估算全程仍不得改写入参时间轴/停机表。"""
    calendar = _IdentityCalendar()
    op, batch = _entities(setup_hours=0.5)
    machine_segments = [(_dt(h), _dt(h + 1)) for h in range(50)]
    operator_segments = [(_dt(h), _dt(h + 1)) for h in range(10, 30)]
    downtimes = [(_dt(20), _dt(26)), (_dt(24), _dt(52))]  # 互相重叠的停机段
    machine_before = list(machine_segments)
    operator_before = list(operator_segments)
    downtimes_before = list(downtimes)

    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id="M1",
        operator_id="O1",
        base_time=_dt(0),
        prev_end=_dt(0),
        machine_timeline=machine_segments,
        operator_timeline=operator_segments,
        end_dt_exclusive=None,
        machine_downtimes=downtimes,
        last_op_type_by_machine=None,
        abort_after=None,
    )

    assert estimate.start_time == _dt(52)
    assert estimate.end_time == _dt(52.5)
    assert machine_segments == machine_before
    assert operator_segments == operator_before
    assert downtimes == downtimes_before
