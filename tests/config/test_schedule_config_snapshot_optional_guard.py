"""回归测试：build_schedule_config_snapshot 对配置字段的可观测降级契约——relaxed 模式下显式 None 的可选字段回退默认并记 blank_required，空白选项/yesno 记 blank_required、非法选项记 invalid_choice（counters 与 degradation_events 同步）；strict 模式下显式 None 必填字段抛 ValidationError(field=...)；repo.get 返回缺 config_value 的记录则两种模式都抛 TypeError。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot


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
    return default_snapshot_values()


def _event_codes_by_field(snapshot):
    return {
        str(event.get("field") or ""): str(event.get("code") or "")
        for event in (snapshot.degradation_events or ())
    }


def _build_snapshot(values, *, strict_mode: bool):
    defaults = _build_defaults()
    repo_values = dict(defaults)
    repo_values.update(values or {})
    return build_schedule_config_snapshot(
        _RepoStub(repo_values),
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
    assert snapshot.degradation_counters == {"blank_required": 1}
    assert _event_codes_by_field(snapshot) == {field: "blank_required"}


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
    assert counters == {"invalid_choice": 3}
    assert _event_codes_by_field(snapshot) == {
        "sort_strategy": "invalid_choice",
        "dispatch_mode": "invalid_choice",
        "auto_assign_enabled": "invalid_choice",
    }


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
    assert counters == {"blank_required": 2}
    assert _event_codes_by_field(snapshot) == {
        "dispatch_rule": "blank_required",
        "freeze_window_enabled": "blank_required",
    }


@pytest.mark.parametrize("strict_mode", (False, True))
def test_build_schedule_config_snapshot_rejects_repo_records_without_config_value(strict_mode: bool) -> None:
    defaults = _build_defaults()

    with pytest.raises(TypeError, match=r"repo\.get\(sort_strategy\).*config_value"):
        build_schedule_config_snapshot(
            _InvalidRepoStub(),
            defaults=defaults,
            strict_mode=strict_mode,
        )
