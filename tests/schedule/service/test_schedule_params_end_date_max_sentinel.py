"""回归测试：排产窗口截止日期的 9999-12-31 哨兵合同（A05）——_resolve_end_dt_exclusive 对
date.max 同日（ERP 常用"无截止"哨兵）复用 due_exclusive 口径显式返回 datetime.max（语义
"不设上限"），strict / 非 strict 两模式都不得抛 OverflowError 且不产生降级 warning；
9999-12-30 等普通日期仍按当日 0 点 +1 天作排他上界；resolve_schedule_params 全链同样成立。"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from core.algorithms.greedy.schedule_params import (
    _resolve_end_dt_exclusive,
    resolve_schedule_params,
)
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot


def _build_snapshot(**overrides) -> ScheduleConfigSnapshot:
    data = {
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
    data.update(overrides)
    return ScheduleConfigSnapshot(**data)


@pytest.mark.parametrize("strict_mode", [False, True])
@pytest.mark.parametrize(
    "end_date",
    ["9999-12-31", date(9999, 12, 31), datetime(9999, 12, 31, 8, 0, 0)],
    ids=["str", "date", "datetime"],
)
def test_end_date_max_sentinel_returns_datetime_max(strict_mode, end_date) -> None:
    warnings: list = []

    result = _resolve_end_dt_exclusive(
        end_date,
        strict_mode=strict_mode,
        warnings=warnings,
        algo_stats=None,
    )

    assert result == datetime.max, "9999-12-31 哨兵应返回 datetime.max（不设上限），而不是 +1 天溢出"
    assert warnings == [], "哨兵是已定义语义（不设上限），不是降级，不应产生 warning"


@pytest.mark.parametrize("strict_mode", [False, True])
def test_end_date_day_before_sentinel_still_plus_one_day(strict_mode) -> None:
    result = _resolve_end_dt_exclusive(
        "9999-12-30",
        strict_mode=strict_mode,
        warnings=[],
        algo_stats=None,
    )

    assert result == datetime(9999, 12, 31, 0, 0, 0), "哨兵只精确到 9999-12-31 这一天，临近日期仍走 +1 天口径"


@pytest.mark.parametrize("strict_mode", [False, True])
def test_resolve_schedule_params_accepts_max_sentinel_end_date(strict_mode) -> None:
    params = resolve_schedule_params(
        config=_build_snapshot(),
        strategy=None,
        strategy_params=None,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date="9999-12-31",
        dispatch_mode=None,
        dispatch_rule=None,
        resource_pool=None,
        algo_stats=None,
        strict_mode=strict_mode,
    )

    assert params.end_dt_exclusive == datetime.max
