from __future__ import annotations

from typing import cast

import pytest

import core.services.common.field_parse as field_parse_mod
from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector


def test_parse_field_float_non_strict_invalid_number_compat_fallback_visible() -> None:
    collector = DegradationCollector()

    result = field_parse_mod.parse_field_float(
        "bad",
        field="priority_weight",
        strict_mode=False,
        scope="scheduler.config_snapshot",
        fallback=0.4,
        collector=collector,
        min_value=0.0,
    )

    assert result == 0.4
    events = collector.to_list()
    assert len(events) == 1, events
    assert events[0].code == "invalid_number", events
    assert collector.to_counters() == {"invalid_number": 1}, collector.to_counters()


def test_parse_field_float_min_violation_uses_precise_reason_and_single_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"required": 0, "compat": 0}

    def fake_required_float(value, *, field, min_value=None, min_inclusive=True):
        calls["required"] += 1
        return 0.0

    def fake_compat_float(*args, **kwargs):
        calls["compat"] += 1
        raise AssertionError("最小值违反不应再回流到 parse_compat_float")

    monkeypatch.setattr(field_parse_mod, "parse_required_float", fake_required_float)
    monkeypatch.setattr(field_parse_mod, "parse_compat_float", fake_compat_float)

    collector = DegradationCollector()
    result = field_parse_mod.parse_field_float(
        "0",
        field="priority_weight",
        strict_mode=False,
        scope="scheduler.config_snapshot",
        fallback=0.4,
        collector=collector,
        min_value=0.1,
    )

    assert result == 0.4
    assert calls == {"required": 1, "compat": 0}, calls
    events = collector.to_list()
    assert len(events) == 1, events
    assert events[0].code == "number_below_minimum", events
    assert collector.to_counters() == {"number_below_minimum": 1}, collector.to_counters()


def test_parse_field_int_strict_mode_still_fast_fail() -> None:
    collector = DegradationCollector()

    with pytest.raises(ValidationError) as exc_info:
        field_parse_mod.parse_field_int(
            "-1",
            field="freeze_window_days",
            strict_mode=True,
            scope="scheduler.config_snapshot",
            fallback=0,
            collector=collector,
            min_value=0,
        )

    assert exc_info.value.field == "freeze_window_days"


def test_parse_field_requires_collector() -> None:
    with pytest.raises(TypeError):
        field_parse_mod.parse_field_float(
            "1",
            field="priority_weight",
            strict_mode=False,
            scope="scheduler.config_snapshot",
            fallback=0.4,
            collector=cast(DegradationCollector, None),
        )

    with pytest.raises(TypeError):
        field_parse_mod.parse_field_int(
            "1",
            field="freeze_window_days",
            strict_mode=False,
            scope="scheduler.config_snapshot",
            fallback=0,
            collector=cast(DegradationCollector, None),
        )
