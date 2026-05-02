from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import default_snapshot_values, list_config_fields
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.config.config_validator import normalize_preset_snapshot
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot


class _EmptyRepo:
    def get_value(self, key, default=None):
        return default


class _ValueRepo:
    def __init__(self, values):
        self._values = dict(values or {})

    def get_value(self, key, default=None):
        return self._values.get(key, default)


def _make_snapshot(**overrides) -> ScheduleConfigSnapshot:
    values = {
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
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }
    values.update(overrides)
    return ScheduleConfigSnapshot(**values)


def test_registry_keys_match_snapshot_projection_keys() -> None:
    registry_keys = [spec.key for spec in list_config_fields()]
    default_keys = list(default_snapshot_values().keys())
    snapshot_keys = list(_make_snapshot().to_dict().keys())
    built_snapshot_keys = list(build_schedule_config_snapshot(_EmptyRepo()).to_dict().keys())

    assert snapshot_keys == registry_keys
    assert default_keys == registry_keys
    assert built_snapshot_keys == registry_keys


def test_strict_snapshot_rejects_inconsistent_weight_triplet() -> None:
    payload = _make_snapshot(priority_weight=0.4, due_weight=0.5, ready_weight=0.9).to_dict()

    with pytest.raises(ValidationError) as build_exc:
        build_schedule_config_snapshot(_ValueRepo(payload), strict_mode=True)
    with pytest.raises(ValidationError) as ensure_exc:
        ensure_schedule_config_snapshot(payload, strict_mode=True)

    assert build_exc.value.field == "权重"
    assert ensure_exc.value.field == "权重"


def test_strict_preset_normalization_rejects_invalid_or_mismatched_ready_weight() -> None:
    base = _make_snapshot()
    invalid_ready = base.to_dict()
    invalid_ready["ready_weight"] = "abc"
    mismatched_ready = base.to_dict()
    mismatched_ready["ready_weight"] = 0.9

    with pytest.raises(ValidationError) as invalid_exc:
        normalize_preset_snapshot(invalid_ready, base=base, strict_mode=True)
    with pytest.raises(ValidationError) as mismatch_exc:
        normalize_preset_snapshot(mismatched_ready, base=base, strict_mode=True)

    assert invalid_exc.value.field == "ready_weight"
    assert mismatch_exc.value.field == "权重"


def test_service_snapshot_preserves_model_runtime_degradation_events() -> None:
    from core.models.schedule_config_runtime import ScheduleConfigSnapshot as RuntimeScheduleConfigSnapshot

    event = {
        "code": "invalid_choice",
        "scope": "scheduler.runtime_config",
        "field": "dispatch_mode",
        "message": "字段“dispatch_mode”取值不正确，本次先按安全值处理。",
        "count": 2,
        "sample": "'bad'",
    }
    runtime_snapshot = RuntimeScheduleConfigSnapshot(
        **_make_snapshot(
            degradation_events=(event,),
            degradation_counters={"invalid_choice": 2},
        ).__dict__
    )

    normalized = ensure_schedule_config_snapshot(runtime_snapshot, strict_mode=False)

    assert normalized.degradation_events == (event,)
    assert normalized.degradation_counters == {"invalid_choice": 2}
