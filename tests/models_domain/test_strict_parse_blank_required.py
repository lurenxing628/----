"""回归测试：core.services.common.strict_parse 的必填/可选解析器——parse_required_float/int/date 对 None/空白/NaN/小数形整数/低于 min_value/非法日期时间抛带正确中文 field 的 ValidationError，整数形浮点串可解析为 int、2026/03/05 归一化为 ISO；parse_optional_* 遇空白返回 None。"""


def _expect_validation(label, func, field: str) -> None:
    from core.infrastructure.errors import ValidationError

    try:
        func()
    except ValidationError as exc:
        assert exc.field == field, f"{label} 字段异常：{exc.field!r}"
        return
    raise AssertionError(f"{label} 应抛出 ValidationError(field={field!r})")


def test_strict_parse_blank_required() -> None:

    from core.services.common.strict_parse import (
        parse_optional_date,
        parse_optional_float,
        parse_optional_int,
        parse_required_date,
        parse_required_float,
        parse_required_int,
    )

    _expect_validation("required_float.none", lambda: parse_required_float(None, field="默认周期"), "默认周期")
    _expect_validation("required_float.blank", lambda: parse_required_float("   ", field="默认周期"), "默认周期")
    _expect_validation("required_float.nan", lambda: parse_required_float("NaN", field="默认周期"), "默认周期")
    _expect_validation(
        "required_float.min_value",
        lambda: parse_required_float("0.4", field="默认周期", min_value=0.5),
        "默认周期",
    )
    assert parse_optional_float("", field="默认周期") is None, "optional float 空白应返回 None"
    assert abs(parse_required_float("1.25", field="默认周期", min_value=0.5) - 1.25) < 1e-9, "required float 解析异常"

    assert parse_required_int("12.0", field="锁定天数") == 12, "默认应继续支持整数形浮点字符串"
    assert parse_required_int(12.0, field="锁定天数") == 12, "默认应继续支持整数形浮点数"
    assert parse_required_int("12.0", field="锁定天数", reject_integer_float=False) == 12
    assert parse_required_int("12", field="锁定天数", reject_integer_float=True) == 12
    assert parse_required_int(12, field="锁定天数", reject_integer_float=True) == 12
    _expect_validation(
        "required_int.reject_integer_float_text",
        lambda: parse_required_int("12.0", field="锁定天数", reject_integer_float=True),
        "锁定天数",
    )
    _expect_validation(
        "required_int.reject_integer_float_number",
        lambda: parse_required_int(12.0, field="锁定天数", reject_integer_float=True),
        "锁定天数",
    )
    _expect_validation("required_int.decimal", lambda: parse_required_int("12.5", field="锁定天数"), "锁定天数")
    _expect_validation(
        "required_int.min_value",
        lambda: parse_required_int("0", field="锁定天数", min_value=1),
        "锁定天数",
    )
    assert parse_optional_int("  ", field="锁定天数") is None, "optional int 空白应返回 None"

    parsed_date = parse_required_date("2026/03/05", field="交期")
    assert parsed_date.isoformat() == "2026-03-05", f"日期解析异常：{parsed_date!r}"
    assert parse_optional_date("", field="交期") is None, "optional date 空白应返回 None"
    _expect_validation(
        "required_date.invalid_time",
        lambda: parse_required_date("2026-03-05 12:00", field="交期"),
        "交期",
    )
