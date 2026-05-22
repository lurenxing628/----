from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
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
