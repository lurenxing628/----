"""
回归测试：Greedy 日期解析工具独立化后保持兼容语义（F03）。
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime


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

    from core.algorithms.greedy.date_parsers import parse_date, parse_datetime
    from core.algorithms.greedy.schedule_params import parse_date as parse_date_compat
    from core.algorithms.greedy.schedule_params import parse_datetime as parse_datetime_compat

    d = parse_date("2026-02-14")
    assert d == date(2026, 2, 14), d
    assert parse_date("2026/02/14") == date(2026, 2, 14)
    assert parse_date(datetime(2026, 2, 14, 8, 30, 0)) == date(2026, 2, 14)
    assert parse_date("bad-date") is None

    dt = parse_datetime("2026-02-14 08:30")
    assert dt == datetime(2026, 2, 14, 8, 30, 0), dt
    assert parse_datetime("2026-02-14T08:30") == datetime(2026, 2, 14, 8, 30, 0)
    assert parse_datetime("2026/02/14 08:30:11") == datetime(2026, 2, 14, 8, 30, 11)
    assert parse_datetime("2026-02-14") == datetime(2026, 2, 14, 0, 0, 0)
    assert parse_datetime("invalid") is None

    # 兼容导出：外部继续从 schedule_params 导入解析函数。
    assert parse_date_compat("2026-02-14") == date(2026, 2, 14)
    assert parse_datetime_compat("2026-02-14 08:30") == datetime(2026, 2, 14, 8, 30, 0)

    print("OK")


if __name__ == "__main__":
    main()

