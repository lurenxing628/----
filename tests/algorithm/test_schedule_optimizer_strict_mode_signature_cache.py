"""回归测试：_schedule_with_optional_strict_mode 按调度器签名自适应传参并缓存——支持 strict_mode 的绑定方法只调一次 inspect.signature 并缓存、legacy 调度器不收 strict_mode；readiness_gate_enabled=False 时静默丢弃、=True 时对不支持者抛 ValidationError（含「不支持 readiness_gate_enabled」），graph_ready_context 不支持时抛含「工序图 ready 队列」的错误；签名不可用时按 unexpected keyword 逐步回退试 strict_mode/readiness，但不吞掉调度器函数体自身抛的 TypeError，且不可哈希的可调用 schedule 不进缓存。"""

from __future__ import annotations

import inspect
from typing import Any, List

import pytest

import core.services.scheduler.run.schedule_signature_support as signature_support
from core.infrastructure.errors import ValidationError
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


class _UnknownReadinessLegacyScheduler:
    def __init__(self) -> None:
        self.calls: List[Any] = []

    def schedule(self, **kwargs):
        self.calls.append(dict(kwargs))
        if "readiness_gate_enabled" in kwargs:
            raise TypeError("schedule() got an unexpected keyword argument 'readiness_gate_enabled'")
        return {"ok": True, "kwargs": dict(kwargs)}


class _UnknownLegacyNoStrictNoReadinessScheduler:
    def __init__(self) -> None:
        self.calls: List[Any] = []

    def schedule(self, **kwargs):
        self.calls.append(dict(kwargs))
        if "strict_mode" in kwargs:
            raise TypeError("schedule() got an unexpected keyword argument 'strict_mode'")
        if "readiness_gate_enabled" in kwargs:
            raise TypeError("schedule() got an unexpected keyword argument 'readiness_gate_enabled'")
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


def test_legacy_scheduler_drops_disabled_readiness_keyword() -> None:
    scheduler = _LegacyScheduler()

    assert _schedule_with_optional_strict_mode(
        scheduler,
        strict_mode=False,
        readiness_gate_enabled=False,
        value=7,
    ) == {"value": 7}
    assert scheduler.calls == 1


def test_legacy_scheduler_rejects_enabled_readiness_keyword() -> None:
    with pytest.raises(ValidationError, match="不支持 readiness_gate_enabled"):
        _schedule_with_optional_strict_mode(
            _LegacyScheduler(),
            strict_mode=False,
            readiness_gate_enabled=True,
            value=7,
        )


def test_legacy_scheduler_rejects_graph_ready_context_with_graph_message() -> None:
    with pytest.raises(ValidationError, match="工序图 ready 队列"):
        _schedule_with_optional_strict_mode(
            _LegacyScheduler(),
            strict_mode=False,
            graph_ready_context={"enabled": True},
            value=7,
        )


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


def test_unknown_signature_drops_disabled_readiness_after_strict_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        signature_support.inspect,
        "signature",
        lambda obj: (_ for _ in ()).throw(ValueError("signature unavailable")),
    )

    scheduler = _UnknownLegacyNoStrictNoReadinessScheduler()

    assert _schedule_with_optional_strict_mode(
        scheduler,
        strict_mode=True,
        readiness_gate_enabled=False,
        value=9,
    ) == {"ok": True, "kwargs": {"value": 9}}

    assert scheduler.calls == [
        {"value": 9, "readiness_gate_enabled": False, "strict_mode": True},
        {"value": 9, "readiness_gate_enabled": False},
        {"value": 9},
    ]


def test_unknown_signature_only_retries_disabled_readiness_keyword(monkeypatch) -> None:
    monkeypatch.setattr(
        signature_support.inspect,
        "signature",
        lambda obj: (_ for _ in ()).throw(ValueError("signature unavailable")),
    )

    scheduler = _UnknownReadinessLegacyScheduler()
    assert _schedule_with_optional_strict_mode(
        scheduler,
        strict_mode=False,
        readiness_gate_enabled=False,
        value=9,
    ) == {"ok": True, "kwargs": {"value": 9, "strict_mode": False}}
    assert scheduler.calls == [
        {"value": 9, "readiness_gate_enabled": False, "strict_mode": False},
        {"value": 9, "strict_mode": False},
    ]


def test_unknown_signature_rejects_enabled_readiness_keyword(monkeypatch) -> None:
    monkeypatch.setattr(
        signature_support.inspect,
        "signature",
        lambda obj: (_ for _ in ()).throw(ValueError("signature unavailable")),
    )

    with pytest.raises(ValidationError, match="不支持 readiness_gate_enabled"):
        _schedule_with_optional_strict_mode(
            _UnknownReadinessLegacyScheduler(),
            strict_mode=False,
            readiness_gate_enabled=True,
            value=9,
        )


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
