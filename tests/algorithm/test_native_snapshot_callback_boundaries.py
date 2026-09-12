"""An unsupported certificate must never call user metaclass comparisons."""

from types import SimpleNamespace

import pytest

from core.algorithm_runtime.native_snapshot import (
    UNSUPPORTED,
    content_snapshot,
    native_record_snapshot,
    scalar_snapshot,
    scalar_tuple_snapshot,
)
from core.algorithm_runtime.sgs_estimate_reuse import (
    native_multi_start_calendar_snapshot,
    native_sgs_policy_snapshot,
)
from core.services.scheduler.calendar_service import CalendarService
from tests._support.busy_block_case import BASE, native_calendar


def _custom_metaclass_value(calls, *, collide=False):
    class Meta(type):
        def __hash__(self):
            calls.append("hash")
            if collide:
                return hash(CalendarService)
            raise AssertionError("optional certificate called metaclass hash")

        def __eq__(self, other):
            calls.append("eq")
            raise AssertionError("optional certificate called metaclass equality")

    class Value(metaclass=Meta):
        def __getattribute__(self, name):
            calls.append("getattribute")
            raise AssertionError("optional certificate called an unsupported getter")

    return Value()


@pytest.mark.parametrize("entry", ["scalar", "tuple", "record_value", "record_type", "content", "nested_content"])
def test_unknown_metaclass_is_rejected_without_hash_equality_or_getter(entry):
    calls = []
    value = _custom_metaclass_value(calls)
    if entry == "scalar":
        result = scalar_snapshot(value)
    elif entry == "tuple":
        result = scalar_tuple_snapshot((value,), scalar_tuple_snapshot((1,)))
    elif entry == "record_value":
        result = native_record_snapshot(SimpleNamespace(note=value), (SimpleNamespace,))
    elif entry == "record_type":
        result = native_record_snapshot(value, (SimpleNamespace,))
    elif entry == "content":
        result = content_snapshot(value)
    else:
        result = content_snapshot({"extra": [value]})
    assert result is UNSUPPORTED
    assert calls == []


@pytest.mark.parametrize("kind", ["sgs", "multi_start"])
@pytest.mark.parametrize("collide", [False, True])
def test_calendar_registry_rejects_custom_metaclass_before_lookup(kind, collide):
    calls = []
    calendar = _custom_metaclass_value(calls, collide=collide)
    result = (native_sgs_policy_snapshot(calendar, None) if kind == "sgs"
              else native_multi_start_calendar_snapshot(calendar))
    assert result is None
    assert calls == []


def test_native_scalar_and_calendar_certificates_remain_usable():
    values = (None, True, 1, "value", BASE, 1.25)
    original = scalar_tuple_snapshot(values)
    assert original is not UNSUPPORTED
    assert scalar_tuple_snapshot(values, original) is original
    assert native_record_snapshot(SimpleNamespace(note="value"), (SimpleNamespace,)) is not UNSUPPORTED
    with native_calendar() as calendar:
        assert native_sgs_policy_snapshot(calendar, None) is not None
        assert native_multi_start_calendar_snapshot(calendar) is not None
