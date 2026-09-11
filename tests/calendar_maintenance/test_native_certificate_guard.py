"""Compare the native proof shortcut with the original reflected-method proof."""

from datetime import datetime
from types import MethodType
from unittest.mock import patch

import pytest

from core.services.scheduler import calendar_service as service_module
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.scheduler.calendar_service import CalendarService
from tests._support.busy_block_case import BASE, at, day_row, native_calendar


def legacy_certificate(calendar, dt, *, priority="normal", operator_id="O1"):
    if type(calendar) is not CalendarService or type(calendar._engine) is not CalendarEngine:
        return None
    for name, original in service_module._NATIVE_SERVICE_TIMING.items():
        if getattr(getattr(calendar, name), "__func__", None) is not original:
            return None
    for name, original in service_module._NATIVE_ENGINE_TIMING.items():
        if getattr(getattr(calendar._engine, name), "__func__", None) is not original:
            return None
    policy = calendar._engine.policy_for_datetime(dt, operator_id=operator_id)
    if policy.date_str != dt.date().isoformat() or not policy.is_priority_allowed(priority):
        return None
    start, end = policy.work_window()
    if not start <= dt < end:
        return None
    if end.date() != dt.date():
        end = datetime.combine(end.date(), datetime.min.time())
        if (end - dt).days:
            return None
    return start, end


@pytest.mark.parametrize("start,priority,rows", [
    (0, "normal", ()), (9, "normal", ()), (-1, "normal", ()),
    (0, "urgent", (day_row(allow_urgent="no"),)),
    (15, "normal", (day_row(shift_start="22:00", shift_end="06:00"),)),
    (17, "normal", (day_row(shift_start="22:00", shift_end="06:00"),)),
])
def test_native_certificate_values_match_original(start, priority, rows):
    with native_calendar(rows) as calendar:
        dt = at(start)
        expected = legacy_certificate(calendar, dt, priority=priority)
        assert calendar.certified_slot_window(dt, priority=priority, operator_id="O1") == expected


@pytest.mark.parametrize("target,name", [
    ("service", name) for name in service_module._NATIVE_SERVICE_TIMING
] + [("engine", name) for name in service_module._NATIVE_ENGINE_TIMING])
@pytest.mark.parametrize("kind", ["wrapped", "same-binding", "other-binding"])
def test_instance_method_bindings_preserve_the_original_proof(target, name, kind):
    with native_calendar() as calendar, native_calendar() as other:
        owner = calendar if target == "service" else calendar._engine
        donor = other if target == "service" else other._engine
        original = getattr(type(owner), name)
        if kind == "wrapped":
            def wrapped(self, *args, **kwargs):
                return original(self, *args, **kwargs)
            replacement = MethodType(wrapped, owner)
        else:
            replacement = MethodType(original, donor if kind == "other-binding" else owner)
        with patch.object(owner, name, replacement):
            assert not service_module._NATIVE_METHODS_UNCHANGED(calendar)
            expected = legacy_certificate(calendar, BASE)
            actual = calendar.certified_slot_window(BASE, priority="normal", operator_id="O1")
            assert actual == expected


def test_native_method_proof_avoids_bound_method_reflection(monkeypatch):
    calls = []

    def observed(*args):
        calls.append(args)
        return getattr(*args)

    with native_calendar() as calendar:
        monkeypatch.setattr(service_module, "getattr", observed, raising=False)
        expected = legacy_certificate(calendar, BASE)
        assert calendar.certified_slot_window(BASE, priority="normal", operator_id="O1") == expected
        assert calls == []
        with patch.object(calendar, "get_efficiency", calendar.get_efficiency):
            assert calendar.certified_slot_window(BASE, priority="normal", operator_id="O1") == expected
        assert len(calls) == 18


def test_engine_property_keeps_legacy_read_order():
    traces, values = [], []
    for legacy in (True, False):
        with native_calendar() as calendar:
            engine, calls = calendar._engine, []

            def read_engine(self):
                calls.append("engine")
                return engine

            with patch.object(CalendarService, "_engine", property(read_engine), create=True):
                if legacy:
                    value = legacy_certificate(calendar, BASE)
                else:
                    value = calendar.certified_slot_window(BASE, priority="normal", operator_id="O1")
            values.append(value)
            traces.append(calls)
    assert values[0] == values[1]
    assert traces[0] == traces[1]
