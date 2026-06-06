"""回归测试：parse_compat_float/parse_compat_date 在脏值（非数字、空白、非法日期）下按字段回退到默认值，并向 DegradationCollector 记下 invalid_number/legacy_external_days_defaulted/blank_required/invalid_due_date 退化码、计数各 1，且面向用户的退化文案用业务口径（供应商默认周期/外协周期/优先级权重/交期）而不泄露内部字段名或开发口径。"""


def test_compat_parse_emits_degradation() -> None:

    from core.services.common.compat_parse import parse_compat_date, parse_compat_float
    from core.services.common.degradation import DegradationCollector

    collector = DegradationCollector()

    default_days = parse_compat_float("abc", field="default_days", scope="supplier_history", collector=collector)
    assert abs(float(default_days or 0.0) - 1.0) < 1e-9, f"default_days compat 回退异常：{default_days!r}"

    ext_days = parse_compat_float("bad", field="ext_days", scope="schedule_input", collector=collector)
    assert abs(float(ext_days or 0.0) - 1.0) < 1e-9, f"ext_days compat 回退异常：{ext_days!r}"

    priority_weight = parse_compat_float(
        "   ",
        field="priority_weight",
        scope="config",
        collector=collector,
        fallback=0.4,
        min_value=0.0,
    )
    assert abs(float(priority_weight or 0.0) - 0.4) < 1e-9, f"priority_weight compat 回退异常：{priority_weight!r}"

    due_date = parse_compat_date("2026-02-31", field="due_date", scope="schedule_history", collector=collector)
    assert due_date is None, f"due_date compat 回退异常：{due_date!r}"

    events = collector.to_list()
    codes = [event.code for event in events]
    assert codes == [
        "invalid_number",
        "legacy_external_days_defaulted",
        "blank_required",
        "invalid_due_date",
    ], f"退化原因码异常：{codes!r}"
    messages = [event.message for event in events]
    assert "供应商默认周期" in messages[0], f"供应商默认周期退化文案异常：{messages[0]!r}"
    assert "外协周期" in messages[1], f"外协周期退化文案异常：{messages[1]!r}"
    assert "优先级权重" in messages[2], f"优先级权重退化文案异常：{messages[2]!r}"
    assert "交期" in messages[3], f"交期退化文案异常：{messages[3]!r}"
    forbidden_text = " ".join(messages)
    for internal_key in ("default_days", "ext_days", "priority_weight", "due_date"):
        assert internal_key not in forbidden_text, f"退化文案不应暴露内部字段 {internal_key!r}：{messages!r}"
    assert "兼容读取" not in forbidden_text, f"退化文案不应使用开发口径：{messages!r}"
    assert all(event.sample is not None for event in events), "兼容读取事件应保留样本值"

    counters = collector.to_counters()
    assert counters["invalid_number"] == 1, f"invalid_number 计数异常：{counters!r}"
    assert counters["legacy_external_days_defaulted"] == 1, f"legacy_external_days_defaulted 计数异常：{counters!r}"
    assert counters["blank_required"] == 1, f"blank_required 计数异常：{counters!r}"
    assert counters["invalid_due_date"] == 1, f"invalid_due_date 计数异常：{counters!r}"


