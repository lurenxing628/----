"""
回归测试：Greedy 日期解析工具独立化后保持兼容语义（F03）。
"""

from __future__ import annotations

from datetime import date, datetime


class _BrokenText:
    def __str__(self) -> str:
        raise RuntimeError("date text exploded")


def test_greedy_date_parsers() -> None:

    from core.algorithms.greedy.date_parsers import parse_date, parse_datetime
    from core.algorithms.greedy.schedule_params import parse_date as parse_date_compat
    from core.algorithms.greedy.schedule_params import parse_datetime as parse_datetime_compat

    d = parse_date("2026-02-14")
    assert d == date(2026, 2, 14), d
    assert parse_date("2026/02/14") == date(2026, 2, 14)
    assert parse_date(datetime(2026, 2, 14, 8, 30, 0)) == date(2026, 2, 14)
    assert parse_date("bad-date") is None
    try:
        parse_date(_BrokenText())
    except RuntimeError:
        pass
    else:
        raise AssertionError("日期解析不应吞掉非格式类运行时异常")

    dt = parse_datetime("2026-02-14 08:30")
    assert dt == datetime(2026, 2, 14, 8, 30, 0), dt
    assert parse_datetime("2026-02-14T08:30") == datetime(2026, 2, 14, 8, 30, 0)
    assert parse_datetime("2026/02/14 08:30:11") == datetime(2026, 2, 14, 8, 30, 11)
    assert parse_datetime("2026-02-14") == datetime(2026, 2, 14, 0, 0, 0)
    assert parse_datetime("invalid") is None
    try:
        parse_datetime(_BrokenText())
    except RuntimeError:
        pass
    else:
        raise AssertionError("时间解析不应吞掉非格式类运行时异常")

    # 兼容导出：外部继续从 schedule_params 导入解析函数。
    assert parse_date_compat("2026-02-14") == date(2026, 2, 14)
    assert parse_datetime_compat("2026-02-14 08:30") == datetime(2026, 2, 14, 8, 30, 0)


