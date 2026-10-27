"""配置快照的代表性非法数值与空白选项处理。"""

from __future__ import annotations

import enum
from decimal import Decimal

import pytest

from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.services.common.excel_validators import get_batch_row_validate_and_normalize
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from core.shared.strict_parse import (
    integer_value,
    is_exact_finite_number,
    is_exact_non_negative_number,
    parse_required_int,
)


class _One(enum.IntEnum):
    ONE = 1


class _Real(float):
    pass


def _expect_validation(label, func, field, message_contains=None, forbidden_message_text=None):
    from core.errors import ValidationError

    try:
        func()
    except ValidationError as exc:
        assert exc.field == field, f"{label} 字段异常：{exc.field!r}"
        if message_contains:
            assert message_contains in exc.message, f"{label} 提示未包含 {message_contains!r}：{exc.message!r}"
        if forbidden_message_text:
            assert forbidden_message_text not in exc.message, f"{label} 提示泄露内部字段：{exc.message!r}"
        return
    raise AssertionError(f"{label} 应抛出 ValidationError(field={field!r})")


def test_config_snapshot_strict_numeric() -> None:
    defaults = default_snapshot_values()

    def _build(values):
        rows = [{"config_key": key, "config_value": value} for key, value in values.items()]
        return build_schedule_config_snapshot(rows=rows)

    _expect_validation(
        "strict.priority_weight",
        lambda: _build({**defaults, "priority_weight": "abc"}),
        "priority_weight",
        message_contains="优先级权重",
        forbidden_message_text="priority_weight",
    )
    _expect_validation(
        "strict.dispatch_mode.blank",
        lambda: _build({**defaults, "dispatch_mode": "   "}),
        "dispatch_mode",
    )


def test_strict_integer_parse_keeps_integers_beyond_float_precision_exact() -> None:
    # 2**53 + 1 is the first integer a float round-trip silently turns into 2**53.
    exact = 2**53 + 1
    assert parse_required_int(exact, field="工序编号") == exact
    assert parse_required_int(str(exact), field="工序编号") == exact
    assert parse_required_int(f"{exact}.0", field="工序编号") == exact
    assert integer_value(f"{exact}.0") == exact
    assert integer_value("1.0000000001") is None
    _expect_validation(
        "fractional.near_integer",
        lambda: parse_required_int("1.0000000001", field="工序编号"),
        "工序编号",
        message_contains="必须是整数",
    )
    validator = get_batch_row_validate_and_normalize(parts_cache={"P001": {"part_name": "零件"}})
    fractional_row = {"批次号": "B1", "图号": "P001", "数量": "1.0000000001", "优先级": "普通", "维护齐套标记": "齐套"}
    assert validator(fractional_row) == "“数量”必须是整数"
    exact_row = {"批次号": "B1", "图号": "P001", "数量": str(exact), "优先级": "普通", "维护齐套标记": "齐套"}
    assert validator(exact_row) is None and exact_row["数量"] == exact
    # The config snapshot reads stored integer text through the min_value path.
    rows = [
        {"config_key": key, "config_value": value}
        for key, value in {**default_snapshot_values(), "time_budget_seconds": str(exact)}.items()
    ]
    assert build_schedule_config_snapshot(rows=rows).time_budget_seconds == exact

    # Float-shaped input keeps the float route and its integer-float rejection.
    assert parse_required_int("1.0", field="工序编号") == 1
    _expect_validation(
        "reject_integer_float.text",
        lambda: parse_required_int("1.0", field="工序编号", reject_integer_float=True),
        "工序编号",
        message_contains="必须是整数",
    )
    _expect_validation(
        "reject_integer_float.float",
        lambda: parse_required_int(1.0, field="工序编号", reject_integer_float=True),
        "工序编号",
        message_contains="必须是整数",
    )
    _expect_validation("bool", lambda: parse_required_int(True, field="工序编号"), "工序编号", message_contains="必须是整数")


@pytest.mark.parametrize(
    ("value", "finite", "non_negative", "positive"),
    [
        (0, True, True, False),
        (-0.0, True, True, False),
        (1.5, True, True, True),
        (-1, True, False, False),
        (2**63, True, True, True),
        (1e308, True, True, True),
        # Ints beyond the float range are refused instead of letting math.isfinite raise OverflowError.
        (10**400, False, False, False),
        (-(10**400), False, False, False),
        (float("nan"), False, False, False),
        (float("inf"), False, False, False),
        (float("-inf"), False, False, False),
        # Only an exact stored / JSON number counts: no bool, text, Decimal or int/float subclass.
        (True, False, False, False),
        (None, False, False, False),
        ("1", False, False, False),
        (Decimal("1"), False, False, False),
        (_One.ONE, False, False, False),
        (_Real(2.5), False, False, False),
    ],
)
def test_exact_finite_number_accepts_only_exact_finite_int_or_float(value, finite, non_negative, positive) -> None:
    assert is_exact_finite_number(value) is finite
    assert is_exact_non_negative_number(value) is non_negative
    assert is_exact_non_negative_number(value, positive=True) is positive
