import os
import sys


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

    from core.algorithms.sort_strategies import SortStrategy, parse_strategy

    assert parse_strategy("WEIGHTED") == SortStrategy.WEIGHTED, "WEIGHTED 大小写容错失败"
    assert parse_strategy(" fifo ") == SortStrategy.FIFO, "FIFO 空白/大小写容错失败"
    assert parse_strategy("Priority_First") == SortStrategy.PRIORITY_FIRST, "PRIORITY_FIRST 容错失败"

    # 未知值回退 default
    assert parse_strategy("unknown", default=SortStrategy.DUE_DATE_FIRST) == SortStrategy.DUE_DATE_FIRST, "未知值 default 回退失败"

    print("OK")


if __name__ == "__main__":
    main()

