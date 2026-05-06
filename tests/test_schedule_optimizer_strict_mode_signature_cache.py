from __future__ import annotations

import inspect
from typing import Any, List

import pytest

import core.services.scheduler.run.schedule_signature_support as signature_support
from core.services.scheduler.run.schedule_optimizer_steps import _schedule_with_optional_strict_mode
from core.services.scheduler.run.schedule_signature_support import clear_strict_mode_support_cache_for_tests


def setup_function() -> None:
    clear_strict_mode_support_cache_for_tests()


class _StrictAwareScheduler:
    def __init__(self) -> None:
        self.strict_mode_values: List[bool] = []

    def schedule(self, *, strict_mode: bool = False, value: int = 0):
        self.strict_mode_values.append(bool(strict_mode))
        return {"strict_mode": bool(strict_mode), "value": int(value)}


class _LegacyScheduler:
    def __init__(self) -> None:
        self.calls = 0

    def schedule(self, *, value: int = 0):
        self.calls += 1
        return {"value": int(value)}


class _UnknownLegacyScheduler:
    def __init__(self) -> None:
        self.calls: List[Any] = []

    def schedule(self, **kwargs):
        self.calls.append(dict(kwargs))
        if "strict_mode" in kwargs:
            raise TypeError("schedule() got an unexpected keyword argument 'strict_mode'")
        return {"ok": True, "kwargs": dict(kwargs)}


class _UnknownBrokenScheduler:
    def schedule(self, **kwargs):
        raise TypeError("boom from scheduler body")


class _UnhashableScheduleCallable:
    __hash__ = None

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *, strict_mode: bool = False):
        self.calls += 1
        return bool(strict_mode)


class _CallableObjectScheduler:
    def __init__(self) -> None:
        self.schedule = _UnhashableScheduleCallable()


def test_strict_mode_signature_is_cached_for_bound_methods(monkeypatch) -> None:
    calls = []
    original_signature = inspect.signature

    def _counting_signature(obj):
        calls.append(obj)
        return original_signature(obj)

    monkeypatch.setattr(signature_support.inspect, "signature", _counting_signature)

    scheduler = _StrictAwareScheduler()
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=True, value=1) == {"strict_mode": True, "value": 1}
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=False, value=2) == {"strict_mode": False, "value": 2}
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=True, value=3) == {"strict_mode": True, "value": 3}

    assert len(calls) == 1
    assert scheduler.strict_mode_values == [True, False, True]


def test_legacy_scheduler_does_not_receive_strict_mode_keyword(monkeypatch) -> None:
    calls = []
    original_signature = inspect.signature

    def _counting_signature(obj):
        calls.append(obj)
        return original_signature(obj)

    monkeypatch.setattr(signature_support.inspect, "signature", _counting_signature)

    scheduler = _LegacyScheduler()
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=True, value=7) == {"value": 7}
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=False, value=8) == {"value": 8}

    assert len(calls) == 1
    assert scheduler.calls == 2


def test_unknown_signature_keeps_unexpected_keyword_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        signature_support.inspect,
        "signature",
        lambda obj: (_ for _ in ()).throw(ValueError("signature unavailable")),
    )

    scheduler = _UnknownLegacyScheduler()
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=True, value=9) == {
        "ok": True,
        "kwargs": {"value": 9},
    }
    assert scheduler.calls == [{"value": 9, "strict_mode": True}, {"value": 9}]


def test_unknown_signature_does_not_swallow_scheduler_body_type_error(monkeypatch) -> None:
    monkeypatch.setattr(
        signature_support.inspect,
        "signature",
        lambda obj: (_ for _ in ()).throw(ValueError("signature unavailable")),
    )

    with pytest.raises(TypeError, match="boom from scheduler body"):
        _schedule_with_optional_strict_mode(_UnknownBrokenScheduler(), strict_mode=True)


def test_unhashable_callable_schedule_is_not_cached(monkeypatch) -> None:
    calls = []
    original_signature = inspect.signature

    def _counting_signature(obj):
        calls.append(obj)
        return original_signature(obj)

    monkeypatch.setattr(signature_support.inspect, "signature", _counting_signature)

    scheduler = _CallableObjectScheduler()
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=True) is True
    assert _schedule_with_optional_strict_mode(scheduler, strict_mode=False) is False

    assert len(calls) == 2
    assert scheduler.schedule.calls == 2
