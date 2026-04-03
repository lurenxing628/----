import os
import sys


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

    from core.infrastructure.errors import ValidationError
    from core.services.common import number_utils

    calls = []

    original_required_float = number_utils.parse_required_float
    original_optional_float = number_utils.parse_optional_float
    original_required_int = number_utils.parse_required_int
    original_optional_int = number_utils.parse_optional_int

    def fake_required_float(value, *, field, min_value=None):
        calls.append(("required_float", value, field, min_value))
        return 1.25

    def fake_optional_float(value, *, field, min_value=None):
        calls.append(("optional_float", value, field, min_value))
        return 2.5

    def fake_required_int(value, *, field, min_value=None):
        calls.append(("required_int", value, field, min_value))
        return 7

    def fake_optional_int(value, *, field, min_value=None):
        calls.append(("optional_int", value, field, min_value))
        return 9

    try:
        number_utils.parse_required_float = fake_required_float
        number_utils.parse_optional_float = fake_optional_float
        number_utils.parse_required_int = fake_required_int
        number_utils.parse_optional_int = fake_optional_int

        assert abs(number_utils.parse_finite_float("raw_float", field="默认周期", allow_none=False) - 1.25) < 1e-9
        optional_float_value = number_utils.parse_finite_float("raw_optional_float", field="默认周期", allow_none=True)
        assert optional_float_value is not None, "allow_none=True 的门面转调测试应返回浮点值"
        assert abs(optional_float_value - 2.5) < 1e-9
        assert number_utils.parse_finite_int("raw_int", field="锁定天数", allow_none=False) == 7
        assert number_utils.parse_finite_int("raw_optional_int", field="锁定天数", allow_none=True) == 9
    finally:
        number_utils.parse_required_float = original_required_float
        number_utils.parse_optional_float = original_optional_float
        number_utils.parse_required_int = original_required_int
        number_utils.parse_optional_int = original_optional_int

    assert calls == [
        ("required_float", "raw_float", "默认周期", None),
        ("optional_float", "raw_optional_float", "默认周期", None),
        ("required_int", "raw_int", "锁定天数", None),
        ("optional_int", "raw_optional_int", "锁定天数", None),
    ], f"number_utils 未转调 strict_parse 门面：{calls!r}"

    assert number_utils.parse_finite_float("   ", field="默认周期", allow_none=True) is None, "allow_none=True 应保留可空语义"
    assert number_utils.parse_finite_int("   ", field="锁定天数", allow_none=True) is None, "allow_none=True 应保留可空语义"

    try:
        number_utils.parse_finite_float("   ", field="默认周期", allow_none=False)
    except ValidationError as exc:
        assert exc.field == "默认周期", f"严格空白校验字段异常：{exc.field!r}"
    else:
        raise AssertionError("parse_finite_float allow_none=False 遇到空白应抛出 ValidationError")

    print("OK")


if __name__ == "__main__":
    main()
