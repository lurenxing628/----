"""回归测试：三处 due_exclusive 实现（greedy.date_parsers、report.calculations、scheduler.schedule_summary）对 None 截止时间与 9999-12-31 哨兵交期（date.max，ERP 常用"无交期"）统一返回 datetime.max，守护「无交期视为最晚」的共享语义不分叉、不因 +1 天溢出 OverflowError。"""

from datetime import date, datetime


def test_due_exclusive_guard_contract() -> None:

    from core.algorithms.greedy.date_parsers import due_exclusive
    from core.services.report.calculations import due_exclusive as calculations_due_exclusive
    from core.services.scheduler.summary.schedule_summary import due_exclusive as summary_due_exclusive

    expected = datetime.max
    assert due_exclusive(None) == expected, "共享 due_exclusive(None) 应返回 datetime.max"
    assert summary_due_exclusive(None) == expected, "schedule_summary._due_exclusive(None) 应返回 datetime.max"
    assert calculations_due_exclusive(None) == expected, "calculations.due_exclusive(None) 应返回 datetime.max"


def test_due_exclusive_max_due_sentinel_returns_datetime_max() -> None:
    """9999-12-31（date.max 的日期）是 ERP 常见"无交期"哨兵：三处实现都必须显式返回 datetime.max，而不是 +1 天抛 OverflowError。"""

    from core.algorithms.greedy.date_parsers import due_exclusive
    from core.services.report.calculations import due_exclusive as calculations_due_exclusive
    from core.services.scheduler.summary.schedule_summary import due_exclusive as summary_due_exclusive

    expected = datetime.max
    sentinel_date = date(9999, 12, 31)
    sentinel_datetime = datetime(9999, 12, 31, 8, 0, 0)

    assert due_exclusive(sentinel_date) == expected, "共享 due_exclusive(9999-12-31) 应返回 datetime.max"
    assert summary_due_exclusive(sentinel_date) == expected, "schedule_summary due_exclusive(9999-12-31) 应返回 datetime.max"
    assert calculations_due_exclusive(sentinel_date) == expected, "calculations.due_exclusive(9999-12-31) 应返回 datetime.max"

    # datetime 形态的哨兵同样不得溢出（overdue_calculations 的入参就是 parse_dt 出的 datetime）
    assert due_exclusive(sentinel_datetime) == expected, "共享 due_exclusive(datetime 哨兵) 应返回 datetime.max"
    assert calculations_due_exclusive(sentinel_datetime) == expected, "calculations.due_exclusive(datetime 哨兵) 应返回 datetime.max"

    # 哨兵只精确到 9999-12-31 这一天：临近日期仍走正常 +1 天口径
    assert due_exclusive(date(9999, 12, 30)) == datetime(9999, 12, 31, 0, 0, 0)
    assert calculations_due_exclusive(datetime(9999, 12, 30, 0, 0, 0)) == datetime(9999, 12, 31, 0, 0, 0)
