"""回归测试：greedy 调度的 find_overlap_shift_end 对停机区间做避让时，空区间(end==start)与逆序区间(end<start)不应被误判为重叠返回 shift，只有合法重叠区间才返回其结束时刻。"""

from datetime import datetime


def test_downtime_overlap_skips_invalid_segments() -> None:

    from core.algorithms.greedy.downtime import find_overlap_shift_end

    start = datetime(2026, 1, 1, 10, 0, 0)
    end = datetime(2026, 1, 1, 11, 0, 0)

    # 1) 空区间（end==start）：历史实现会误判为重叠并返回 shift
    seg_empty = (datetime(2026, 1, 1, 10, 30, 0), datetime(2026, 1, 1, 10, 30, 0))
    assert find_overlap_shift_end([seg_empty], start, end) is None, "空区间不应造成重叠避让"

    # 2) 逆序区间（end<start）：同样不应造成重叠避让
    seg_reverse = (datetime(2026, 1, 1, 10, 40, 0), datetime(2026, 1, 1, 10, 20, 0))
    assert find_overlap_shift_end([seg_reverse], start, end) is None, "逆序区间不应造成重叠避让"

    # 3) 合法重叠区间：仍应返回其结束时刻
    seg_valid = (datetime(2026, 1, 1, 10, 45, 0), datetime(2026, 1, 1, 12, 0, 0))
    assert find_overlap_shift_end([seg_valid], start, end) == seg_valid[1], "合法重叠区间应触发 shift"
