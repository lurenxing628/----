import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _expect_validation(label, func, field: str) -> None:
    from core.infrastructure.errors import ValidationError

    try:
        func()
    except ValidationError as exc:
        assert exc.field == field, f"{label} 字段异常：{exc.field!r}"
        return
    raise AssertionError(f"{label} 应抛出 ValidationError(field={field!r})")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

    assert parse_required_int("12.0", field="锁定天数") == 12, "整数形浮点字符串应支持解析"
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

    print("OK")


if __name__ == "__main__":
    main()
