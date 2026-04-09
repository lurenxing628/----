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

    from core.algorithms.greedy.date_parsers import due_exclusive
    from core.services.report.calculations import due_exclusive as calculations_due_exclusive
    from core.services.scheduler.schedule_summary import due_exclusive as summary_due_exclusive

    expected = datetime.max
    assert due_exclusive(None) == expected, "共享 due_exclusive(None) 应返回 datetime.max"
    assert summary_due_exclusive(None) == expected, "schedule_summary._due_exclusive(None) 应返回 datetime.max"
    assert calculations_due_exclusive(None) == expected, "calculations.due_exclusive(None) 应返回 datetime.max"

    print("OK")


if __name__ == "__main__":
    main()
