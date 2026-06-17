"""回归测试：三处 due_exclusive 实现（greedy.date_parsers、report.calculations、scheduler.schedule_summary）对 None 截止时间统一返回 datetime.max，守护「无交期视为最晚」的共享语义不分叉。"""

from datetime import datetime


def test_due_exclusive_guard_contract() -> None:

    from core.algorithms.greedy.date_parsers import due_exclusive
    from core.services.report.calculations import due_exclusive as calculations_due_exclusive
    from core.services.scheduler.summary.schedule_summary import due_exclusive as summary_due_exclusive

    expected = datetime.max
    assert due_exclusive(None) == expected, "共享 due_exclusive(None) 应返回 datetime.max"
    assert summary_due_exclusive(None) == expected, "schedule_summary._due_exclusive(None) 应返回 datetime.max"
    assert calculations_due_exclusive(None) == expected, "calculations.due_exclusive(None) 应返回 datetime.max"
