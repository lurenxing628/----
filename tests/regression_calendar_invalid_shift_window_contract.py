from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.services.scheduler.calendar_engine import CalendarEngine


def _engine_with_calendar_row(row):
    engine = CalendarEngine(conn=None)
    engine._resolve_calendar_row = lambda _date_str, _op_id: row  # type: ignore[method-assign]
    return engine


def _calendar_row(**overrides):
    data = {
        "date": "2026-01-01",
        "day_type": "workday",
        "shift_start": "08:00",
        "shift_end": "16:00",
        "shift_hours": 8.0,
        "efficiency": 1.0,
        "allow_normal": "yes",
        "allow_urgent": "yes",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_engine_rejects_non_empty_invalid_shift_start() -> None:
    engine = _engine_with_calendar_row(_calendar_row(shift_start="8点"))

    with pytest.raises(ValidationError) as exc_info:
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))

    assert exc_info.value.field == "班次开始"


def test_engine_rejects_non_empty_invalid_shift_end() -> None:
    engine = _engine_with_calendar_row(_calendar_row(shift_end="18点"))

    with pytest.raises(ValidationError) as exc_info:
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))

    assert exc_info.value.field == "班次结束"


def test_engine_allows_blank_shift_start_default_and_hhmmss() -> None:
    blank_start = _engine_with_calendar_row(_calendar_row(shift_start="", shift_end="16:00:00"))
    policy = blank_start.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))

    assert policy.shift_start.hour == 8
    assert policy.shift_start.minute == 0
    assert policy.shift_hours == 8.0


def test_engine_accepts_full_width_colon_shift_start() -> None:
    engine = _engine_with_calendar_row(_calendar_row(shift_start="07：30", shift_end="15：30"))
    policy = engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))

    assert policy.shift_start.hour == 7
    assert policy.shift_start.minute == 30
    assert policy.shift_hours == 8.0


def test_work_calendar_rejects_negative_shift_hours() -> None:
    with pytest.raises(ValueError, match="shift_hours"):
        WorkCalendar.from_row({"date": "2026-05-01", "shift_hours": "-1", "efficiency": "1"})


def test_work_calendar_rejects_zero_efficiency() -> None:
    with pytest.raises(ValueError, match="efficiency"):
        WorkCalendar.from_row({"date": "2026-05-01", "shift_hours": "8", "efficiency": "0"})


def test_operator_calendar_rejects_negative_efficiency() -> None:
    with pytest.raises(ValueError, match="efficiency"):
        OperatorCalendar.from_row(
            {
                "operator_id": "O1",
                "date": "2026-05-01",
                "shift_hours": "8",
                "efficiency": "-0.5",
            }
        )


def test_blank_calendar_numbers_still_use_business_defaults() -> None:
    cal = WorkCalendar.from_row({"date": "2026-05-01", "shift_hours": "", "efficiency": ""})
    assert cal.shift_hours == 8.0
    assert cal.efficiency == 1.0


def test_engine_rejects_negative_shift_hours() -> None:
    engine = _engine_with_calendar_row(_calendar_row(shift_hours=-1.0))

    with pytest.raises(ValidationError, match="不能为负数"):
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))


def test_engine_rejects_nan_shift_hours() -> None:
    engine = _engine_with_calendar_row(_calendar_row(shift_hours=float("nan")))

    with pytest.raises(ValidationError, match="有限数字"):
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))


def test_engine_rejects_inf_efficiency() -> None:
    engine = _engine_with_calendar_row(_calendar_row(efficiency=float("inf")))

    with pytest.raises(ValidationError, match="有限数字"):
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))


def test_engine_rejects_zero_efficiency() -> None:
    engine = _engine_with_calendar_row(_calendar_row(efficiency=0.0))

    with pytest.raises(ValidationError, match="大于 0"):
        engine.policy_for_datetime(datetime(2026, 1, 1, 9, 0, 0))


def test_add_working_hours_rejects_nan() -> None:
    engine = _engine_with_calendar_row(_calendar_row())

    with pytest.raises(ValidationError, match="有限数字"):
        engine.add_working_hours(datetime(2026, 1, 1, 8, 0, 0), float("nan"))


def test_add_working_hours_rejects_inf() -> None:
    engine = _engine_with_calendar_row(_calendar_row())

    with pytest.raises(ValidationError, match="有限数字"):
        engine.add_working_hours(datetime(2026, 1, 1, 8, 0, 0), float("inf"))


def test_add_calendar_days_rejects_nan() -> None:
    engine = _engine_with_calendar_row(_calendar_row())

    with pytest.raises(ValidationError, match="有限数字"):
        engine.add_calendar_days(datetime(2026, 1, 1, 8, 0, 0), float("nan"))


def test_add_calendar_days_rejects_inf() -> None:
    engine = _engine_with_calendar_row(_calendar_row())

    with pytest.raises(ValidationError, match="有限数字"):
        engine.add_calendar_days(datetime(2026, 1, 1, 8, 0, 0), float("inf"))
