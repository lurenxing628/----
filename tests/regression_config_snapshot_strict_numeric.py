from __future__ import annotations

import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }


def _expect_validation(label, func, field):
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

    from core.services.scheduler.config_snapshot import build_schedule_config_snapshot

    defaults = _default_snapshot_kwargs()
    build_kwargs = {
        "defaults": defaults,
        "valid_strategies": ("priority_first", "due_date_first", "weighted", "fifo"),
        "valid_dispatch_modes": ("batch_order", "sgs"),
        "valid_dispatch_rules": ("slack", "cr", "atc"),
        "valid_algo_modes": ("greedy", "improve"),
        "valid_objectives": ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover"),
    }

    def _build(values, *, strict_mode: bool):
        return build_schedule_config_snapshot(_StubRepo(values), strict_mode=strict_mode, **build_kwargs)

    relaxed = _build(
        {
            "priority_weight": "abc",
            "holiday_default_efficiency": "0",
            "ortools_time_limit_seconds": "0",
            "time_budget_seconds": "0",
            "freeze_window_days": "-3",
        },
        strict_mode=False,
    )
    assert relaxed.priority_weight == defaults["priority_weight"], "非 strict 下非法浮点应回退默认"
    assert relaxed.holiday_default_efficiency == defaults["holiday_default_efficiency"], "非 strict 下 <=0 效率应回退默认"
    assert relaxed.ortools_time_limit_seconds == 1, "非 strict 下 time limit 应保持最小值钳制"
    assert relaxed.time_budget_seconds == 1, "非 strict 下 time budget 应保持最小值钳制"
    assert relaxed.freeze_window_days == 0, "非 strict 下 freeze_window_days 应保持最小值钳制"

    strict_default = _build({}, strict_mode=True)
    assert strict_default.to_dict() == defaults, "strict_mode=True 且未提供坏值时不应破坏默认快照"

    _expect_validation("strict.priority_weight", lambda: _build({"priority_weight": "abc"}, strict_mode=True), "priority_weight")
    _expect_validation("strict.due_weight", lambda: _build({"due_weight": "NaN"}, strict_mode=True), "due_weight")
    _expect_validation(
        "strict.holiday_default_efficiency",
        lambda: _build({"holiday_default_efficiency": "0"}, strict_mode=True),
        "holiday_default_efficiency",
    )
    _expect_validation(
        "strict.ortools_time_limit_seconds",
        lambda: _build({"ortools_time_limit_seconds": "1.5"}, strict_mode=True),
        "ortools_time_limit_seconds",
    )
    _expect_validation(
        "strict.time_budget_seconds",
        lambda: _build({"time_budget_seconds": "0"}, strict_mode=True),
        "time_budget_seconds",
    )
    _expect_validation(
        "strict.freeze_window_days",
        lambda: _build({"freeze_window_days": "-1"}, strict_mode=True),
        "freeze_window_days",
    )

    print("OK")


if __name__ == "__main__":
    main()
