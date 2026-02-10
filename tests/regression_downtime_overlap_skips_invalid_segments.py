import os
import sys
from datetime import datetime


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

    print("OK")


if __name__ == "__main__":
    main()

