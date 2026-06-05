"""回归测试：排序策略对批次 priority 的大小写不敏感——PRIORITY_FIRST 与 WEIGHTED 策略都把 priority='Urgent' 的批次正确识别为高优先级排到 normal 之前。"""

from datetime import date


def test_sort_strategies_priority_case_insensitive() -> None:

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


