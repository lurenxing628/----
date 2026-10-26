"""配置快照的代表性非法数值与空白选项处理。"""

from __future__ import annotations

from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from core.shared.strict_parse import parse_required_int


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
