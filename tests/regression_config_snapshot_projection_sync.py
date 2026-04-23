from __future__ import annotations

from core.services.scheduler.config.config_field_spec import default_snapshot_values, list_config_fields
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot


class _EmptyRepo:
    def get_value(self, key, default=None):
        return default


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
