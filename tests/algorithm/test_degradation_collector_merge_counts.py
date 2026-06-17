"""回归测试：DegradationCollector 对同一 (code, scope, field) 的多次 add（含传入 count 与 DegradationEvent 对象）应按 key 合并为一条，正确累加 count（invalid_number 合并为 4）、保留首个非空 sample，且 to_counters() 按原因码汇总计数。"""


def test_degradation_collector_merge_counts() -> None:

    from core.services.common.degradation import DegradationCollector, DegradationEvent

    collector = DegradationCollector()
    invalid_number_message = "字段“priority_weight”历史数值无效，本次先按 0.4 处理，请检查后保存。"

    collector.add(
        code="invalid_number",
        scope="config",
        field="priority_weight",
        message=invalid_number_message,
    )
    collector.add(
        code="invalid_number",
        scope="config",
        field="priority_weight",
        message=invalid_number_message,
        sample="'bad_value'",
    )
    collector.add(
        DegradationEvent(
            code="invalid_due_date",
            scope="gantt",
            field="due_date",
            message="字段“due_date”历史日期无效，本次先留空，请检查后保存。",
        )
    )
    collector.add(
        code="invalid_number",
        scope="config",
        field="priority_weight",
        message=invalid_number_message,
        count=2,
    )

    events = collector.to_list()
    assert len(events) == 2, f"collector 合并后事件数量异常：{events!r}"

    first = events[0]
    assert first.code == "invalid_number", f"首个事件原因码异常：{first!r}"
    assert first.count == 4, f"invalid_number 合并计数异常：{first.count!r}"
    assert first.sample == "'bad_value'", f"collector 样本保留异常：{first.sample!r}"

    counters = collector.to_counters()
    assert counters == {"invalid_number": 4, "invalid_due_date": 1}, f"collector counters 异常：{counters!r}"
