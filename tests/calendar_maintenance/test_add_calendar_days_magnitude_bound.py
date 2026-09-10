"""回归测试：CalendarEngine.add_calendar_days 的量级上界合同（A11）——有限正巨值（如录入
笔误 9999999 天，能通过 isfinite/非负等全部既有校验）不得再抛裸 OverflowError，须按
ValidationError(field=days) 拒绝并给出中文业务文案"外协周期天数超出合理范围"；上界为
MAX_CALENDAR_DAYS=36500 天（100 年），边界值本身仍可用；NaN/Inf/负数/bool 既有拒绝行为
不回归（Inf 仍命中"有限数字"守卫而非新上界文案，守卫顺序不变）。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.calendar_engine import MAX_CALENDAR_DAYS, CalendarEngine


def _engine() -> CalendarEngine:
    # add_calendar_days 是纯自然日累加，不读日历行，conn=None 即可
    return CalendarEngine(conn=None)


def test_add_calendar_days_rejects_huge_finite_value_with_business_message() -> None:
    with pytest.raises(ValidationError, match="外协周期天数超出合理范围") as exc_info:
        _engine().add_calendar_days(datetime(2026, 7, 20, 8, 0, 0), 9999999)

    assert exc_info.value.field == "days"


def test_add_calendar_days_rejects_just_above_bound() -> None:
    with pytest.raises(ValidationError, match="外协周期天数超出合理范围"):
        _engine().add_calendar_days(datetime(2026, 7, 20, 8, 0, 0), MAX_CALENDAR_DAYS + 0.5)


def test_add_calendar_days_bound_value_100_years_still_usable() -> None:
    start = datetime(2026, 7, 20, 8, 0, 0)

    result = _engine().add_calendar_days(start, MAX_CALENDAR_DAYS)

    assert result == start + timedelta(days=MAX_CALENDAR_DAYS)


def test_add_calendar_days_inf_still_hits_finite_guard_not_bound_message() -> None:
    # 守卫顺序合同：Inf 先被 isfinite 拦下，文案仍是"有限数字"，不落到量级上界分支
    with pytest.raises(ValidationError, match="有限数字"):
        _engine().add_calendar_days(datetime(2026, 7, 20, 8, 0, 0), float("inf"))


def test_add_calendar_days_existing_guards_not_regressed() -> None:
    engine = _engine()
    start = datetime(2026, 7, 20, 8, 0, 0)

    with pytest.raises(ValidationError, match="有限数字"):
        engine.add_calendar_days(start, float("nan"))
    with pytest.raises(ValidationError, match="不能为负数"):
        engine.add_calendar_days(start, -1)
    for bad_value in (True, False):
        with pytest.raises(ValidationError, match="必须是数字"):
            engine.add_calendar_days(start, bad_value)
