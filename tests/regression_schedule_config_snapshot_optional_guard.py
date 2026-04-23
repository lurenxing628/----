from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_snapshot import build_schedule_config_snapshot


class _Record:
    def __init__(self, value) -> None:
        self.config_value = value


class _RepoStub:
    def __init__(self, values) -> None:
        self._values = dict(values or {})

    def get(self, key):
        if key not in self._values:
            return None
        return _Record(self._values[key])


class _InvalidRecord:
    pass


class _InvalidRepoStub:
    def get(self, key):
        if key == "sort_strategy":
            return _InvalidRecord()
        return None


def _build_defaults():
    return {
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
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }


def _build_snapshot(values, *, strict_mode: bool):
    defaults = _build_defaults()
    return build_schedule_config_snapshot(
        _RepoStub(values),
        defaults=defaults,
        strict_mode=strict_mode,
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    (
        ("priority_weight", 0.4),
        ("ortools_time_limit_seconds", 5),
    ),
)
def test_build_schedule_config_snapshot_relaxed_explicit_none_values_fall_back(
    field: str,
    expected,
) -> None:
    snapshot = _build_snapshot({field: None}, strict_mode=False)

    assert getattr(snapshot, field) == expected
    assert sum(int(v) for v in snapshot.degradation_counters.values()) >= 1, snapshot.degradation_counters


@pytest.mark.parametrize("field", ("priority_weight", "ortools_time_limit_seconds"))
def test_build_schedule_config_snapshot_strict_explicit_none_values_raise(field: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _build_snapshot({field: None}, strict_mode=True)

    assert exc_info.value.field == field


def test_build_schedule_config_snapshot_relaxed_invalid_choice_and_yesno_are_observable() -> None:
    snapshot = _build_snapshot(
        {
            "sort_strategy": "bad_strategy",
            "dispatch_mode": "bad_mode",
            "auto_assign_enabled": "maybe",
        },
        strict_mode=False,
    )

    assert snapshot.sort_strategy == "priority_first"
    assert snapshot.dispatch_mode == "batch_order"
    assert snapshot.auto_assign_enabled == "no"

    counters = snapshot.degradation_counters or {}
    assert int(counters.get("invalid_choice") or 0) == 3, counters
    event_codes = {str(event.get("field") or ""): str(event.get("code") or "") for event in (snapshot.degradation_events or ())}
    assert event_codes.get("sort_strategy") == "invalid_choice"
    assert event_codes.get("dispatch_mode") == "invalid_choice"
    assert event_codes.get("auto_assign_enabled") == "invalid_choice"


def test_build_schedule_config_snapshot_relaxed_explicit_blank_choice_and_yesno_emit_blank_required() -> None:
    snapshot = _build_snapshot(
        {
            "dispatch_rule": "   ",
            "freeze_window_enabled": None,
        },
        strict_mode=False,
    )

    assert snapshot.dispatch_rule == "slack"
    assert snapshot.freeze_window_enabled == "no"
    counters = snapshot.degradation_counters or {}
    assert int(counters.get("blank_required") or 0) == 2, counters


@pytest.mark.parametrize("strict_mode", (False, True))
def test_build_schedule_config_snapshot_rejects_repo_records_without_config_value(strict_mode: bool) -> None:
    defaults = _build_defaults()

    with pytest.raises(TypeError, match=r"repo\.get\(sort_strategy\).*config_value"):
        build_schedule_config_snapshot(
            _InvalidRepoStub(),
            defaults=defaults,
            strict_mode=strict_mode,
        )
