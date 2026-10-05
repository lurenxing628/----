"""配置快照的代表性非法数值与空白选项处理。"""

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

    from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot

    defaults = _default_snapshot_kwargs()

    def _build(values, *, strict_mode: bool):
        return build_schedule_config_snapshot(_StubRepo(values), defaults=defaults, strict_mode=strict_mode)

    relaxed = _build(
        {
            "priority_weight": "abc",
            "time_budget_seconds": "0",
        },
        strict_mode=False,
    )
    assert relaxed.priority_weight == defaults["priority_weight"], "非 strict 下非法浮点应回退默认"
    assert relaxed.time_budget_seconds == 1, "非 strict 下 time budget 应保持最小值钳制"


    _expect_validation(
        "strict.priority_weight",
        lambda: _build({**defaults, "priority_weight": "abc"}, strict_mode=True),
        "priority_weight",
        message_contains="优先级权重",
        forbidden_message_text="priority_weight",
    )
    _expect_validation(
        "strict.dispatch_mode.blank",
        lambda: _build({**defaults, "dispatch_mode": "   "}, strict_mode=True),
        "dispatch_mode",
    )
