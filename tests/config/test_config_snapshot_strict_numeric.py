"""回归测试：build_schedule_config_snapshot 在 strict_mode 下对非法数值（priority_weight/due_weight/holiday_default_efficiency/ortools_time_limit_seconds/time_budget_seconds/freeze_window_days/graph_critical_weight/graph_impact_weight 及空白的 sort_strategy/dispatch_mode/dispatch_rule/auto_assign_enabled）抛带正确 field 的 ValidationError 且提示用中文标签不泄露内部字段名；非 strict 下应回退默认或钳到最小值。"""

from __future__ import annotations


class _StubRepo:
    def __init__(self, values):
        self._values = dict(values or {})

    def get_value(self, key, default=None):
        return self._values.get(key, default)


def _default_snapshot_kwargs():
    return {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_debug_export": "no",
    }


def _expect_validation(label, func, field, message_contains=None, forbidden_message_text=None):
    from core.infrastructure.errors import ValidationError

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

    from core.services.scheduler.config_snapshot import build_schedule_config_snapshot

    defaults = _default_snapshot_kwargs()

    def _build(values, *, strict_mode: bool):
        return build_schedule_config_snapshot(_StubRepo(values), defaults=defaults, strict_mode=strict_mode)

    relaxed = _build(
        {
            "priority_weight": "abc",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "0",
            "time_budget_seconds": "0",
            "freeze_window_days": "-3",
            "graph_critical_weight": "-3",
            "graph_impact_weight": "bad",
        },
        strict_mode=False,
    )
    assert relaxed.priority_weight == defaults["priority_weight"], "非 strict 下非法浮点应回退默认"
    assert relaxed.holiday_default_efficiency == defaults["holiday_default_efficiency"], "非 strict 下 <=0 效率应回退默认"
    assert relaxed.ortools_time_limit_seconds == 1, "非 strict 下 time limit 应保持最小值钳制"
    assert relaxed.time_budget_seconds == 1, "非 strict 下 time budget 应保持最小值钳制"
    assert relaxed.freeze_window_days == 0, "非 strict 下 freeze_window_days 应保持最小值钳制"
    assert relaxed.graph_critical_weight == 0, "非 strict 下 graph_critical_weight 应保持最小值钳制"
    assert relaxed.graph_impact_weight == defaults["graph_impact_weight"], "非 strict 下非法图影响权重应回退默认"

    _expect_validation(
        "strict.sort_strategy.missing",
        lambda: _build({}, strict_mode=True),
        "sort_strategy",
    )

    _expect_validation(
        "strict.priority_weight",
        lambda: _build({**defaults, "priority_weight": "abc"}, strict_mode=True),
        "priority_weight",
        message_contains="优先级权重",
        forbidden_message_text="priority_weight",
    )
    _expect_validation(
        "strict.due_weight",
        lambda: _build({**defaults, "due_weight": "NaN"}, strict_mode=True),
        "due_weight",
    )
    _expect_validation(
        "strict.holiday_default_efficiency",
        lambda: _build({**defaults, "holiday_default_efficiency": "0"}, strict_mode=True),
        "holiday_default_efficiency",
    )
    _expect_validation(
        "strict.ortools_time_limit_seconds",
        lambda: _build({**defaults, "ortools_time_limit_seconds": "1.5"}, strict_mode=True),
        "ortools_time_limit_seconds",
    )
    _expect_validation(
        "strict.time_budget_seconds",
        lambda: _build({**defaults, "time_budget_seconds": "0"}, strict_mode=True),
        "time_budget_seconds",
    )
    _expect_validation(
        "strict.freeze_window_days",
        lambda: _build({**defaults, "freeze_window_days": "-1"}, strict_mode=True),
        "freeze_window_days",
        message_contains="锁定天数",
        forbidden_message_text="freeze_window_days",
    )
    _expect_validation(
        "strict.graph_critical_weight",
        lambda: _build({**defaults, "graph_critical_weight": "-1"}, strict_mode=True),
        "graph_critical_weight",
        message_contains="重点工序提前权重",
        forbidden_message_text="graph_critical_weight",
    )
    _expect_validation(
        "strict.graph_impact_weight",
        lambda: _build({**defaults, "graph_impact_weight": "abc"}, strict_mode=True),
        "graph_impact_weight",
        message_contains="后续影响权重",
        forbidden_message_text="graph_impact_weight",
    )
    _expect_validation(
        "strict.sort_strategy.blank",
        lambda: _build({**defaults, "sort_strategy": "   "}, strict_mode=True),
        "sort_strategy",
    )
    _expect_validation(
        "strict.dispatch_mode.blank",
        lambda: _build({**defaults, "dispatch_mode": "   "}, strict_mode=True),
        "dispatch_mode",
    )
    _expect_validation(
        "strict.dispatch_rule.blank",
        lambda: _build({**defaults, "dispatch_rule": "   "}, strict_mode=True),
        "dispatch_rule",
    )
    _expect_validation(
        "strict.auto_assign_enabled.blank",
        lambda: _build({**defaults, "auto_assign_enabled": "   "}, strict_mode=True),
        "auto_assign_enabled",
    )


