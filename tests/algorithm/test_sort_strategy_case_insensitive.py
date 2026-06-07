"""回归测试：SortStrategy.parse_strategy 对策略名大小写/空白容错（WEIGHTED、" fifo "、Priority_First 各自归一），未知值按 default 回退（R51 灵魂线续命测试）。"""


def test_sort_strategy_case_insensitive() -> None:

    from core.algorithms.sort_strategies import SortStrategy, parse_strategy

    assert parse_strategy("WEIGHTED") == SortStrategy.WEIGHTED, "WEIGHTED 大小写容错失败"
    assert parse_strategy(" fifo ") == SortStrategy.FIFO, "FIFO 空白/大小写容错失败"
    assert parse_strategy("Priority_First") == SortStrategy.PRIORITY_FIRST, "PRIORITY_FIRST 容错失败"

    # 未知值回退 default
    assert parse_strategy("unknown", default=SortStrategy.DUE_DATE_FIRST) == SortStrategy.DUE_DATE_FIRST, "未知值 default 回退失败"


