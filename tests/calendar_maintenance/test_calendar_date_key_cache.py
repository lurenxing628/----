"""The bounded cache stores pure native date strings, never calendar policies."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core.services.scheduler.calendar_engine import _native_date_isoformat
from tests._support.busy_block_case import BASE, day_row, native_calendar


@pytest.mark.parametrize("day", [date.min, date.max, date(2024, 2, 29), date(2026, 9, 8)])
def test_native_date_key_is_the_exact_isoformat_value(day):
    assert _native_date_isoformat(day) == day.isoformat()


def test_formatter_cache_is_bounded_and_reuses_native_dates():
    _native_date_isoformat.cache_clear()
    try:
        first = date(2000, 1, 1)
        for offset in range(4100):
            value = first + timedelta(days=offset)
            assert _native_date_isoformat(value) == value.isoformat()
        before = _native_date_isoformat.cache_info()
        assert (before.maxsize, before.currsize) == (4096, 4096)
        assert _native_date_isoformat(first + timedelta(days=4099)) == "2011-03-23"
        assert _native_date_isoformat.cache_info().hits == before.hits + 1
    finally:
        _native_date_isoformat.cache_clear()


def test_mutable_day_policy_is_still_looked_up_on_every_call():
    with native_calendar() as calendar:
        engine = calendar._engine
        first = engine.policy_for_datetime(BASE, operator_id="O1")
        assert first.efficiency == 1.0
        engine._policy_cache.clear()
        replacement = type(first)(BASE.date().isoformat(), "workday", 8.0, 0.5, "yes", "yes")
        engine._policy_cache[("O1", BASE.date().isoformat())] = replacement
        assert engine.policy_for_datetime(BASE, operator_id="O1") is replacement
        assert calendar.get_efficiency(BASE, operator_id="O1") == 0.5


@pytest.mark.parametrize("aware", [False, True])
def test_datetime_date_reads_and_errors_match_uncached_formatter(aware):
    instant = BASE.replace(tzinfo=timezone.utc) if aware else BASE
    outcomes = []
    for cached in (False, True):
        with native_calendar() as calendar:
            formatter = _native_date_isoformat if cached else lambda value: value.isoformat()
            with patch("core.services.scheduler.calendar_engine._native_date_isoformat", formatter):
                try:
                    policy = calendar._engine.policy_for_datetime(instant, operator_id="O1")
                    outcomes.append(("value", policy))
                except Exception as exc:
                    outcomes.append(("error", type(exc), str(exc)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("fail", [False, True])
def test_date_subclass_isoformat_callback_is_not_cached(fail):
    calls = []

    class CustomDate(date):
        def isoformat(self):
            calls.append("isoformat")
            if fail:
                raise RuntimeError("custom date formatting failed")
            return super().isoformat()

    class CustomDatetime(datetime):
        def date(self):
            calls.append("date")
            return CustomDate(self.year, self.month, self.day)

    instant = CustomDatetime(2026, 9, 8, 8)
    with native_calendar([day_row()]) as calendar:
        for _ in range(2):
            if fail:
                with pytest.raises(RuntimeError, match="custom date formatting failed"):
                    calendar._engine.policy_for_datetime(instant, operator_id="O1")
            else:
                assert calendar._engine.policy_for_datetime(instant, operator_id="O1").date_str == "2026-09-08"
    assert calls == ["date", "isoformat", "date", "isoformat"]
