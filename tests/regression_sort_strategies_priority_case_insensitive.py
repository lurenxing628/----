import os
import sys
from datetime import date


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

    from core.algorithms.sort_strategies import BatchForSort, SortStrategy, StrategyFactory

    d = date(2026, 1, 2)
    urgent = BatchForSort(batch_id="B_URGENT", priority="Urgent", due_date=d)
    normal = BatchForSort(batch_id="B_NORMAL", priority="normal", due_date=d)

    s1 = StrategyFactory.create(SortStrategy.PRIORITY_FIRST)
    out1 = [b.batch_id for b in s1.sort([normal, urgent])]
    assert out1[0] == "B_URGENT", f"PRIORITY_FIRST 未正确识别 priority 大小写：{out1!r}"

    s2 = StrategyFactory.create(SortStrategy.WEIGHTED, priority_weight=0.4, due_weight=0.5)
    out2 = [b.batch_id for b in s2.sort([normal, urgent])]
    assert out2[0] == "B_URGENT", f"WEIGHTED 未正确识别 priority 大小写：{out2!r}"

    print("OK")


if __name__ == "__main__":
    main()

