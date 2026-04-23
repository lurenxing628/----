from __future__ import annotations

from pathlib import Path

import pytest

from core.algorithms.objective_specs import objective_choice_labels
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.services.scheduler import ConfigService
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.config_snapshot import (
    ScheduleConfigSnapshot,
    build_schedule_config_snapshot,
)
from core.services.scheduler.config_validator import normalize_preset_snapshot

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _EmptyRepo:
    def get_value(self, key, default=None):
        return default


@pytest.fixture()
def config_service(tmp_path):
    test_db = tmp_path / "aps_config_field_spec.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    try:
        yield ConfigService(conn, logger=None, op_logger=None)
    finally:
        conn.close()


def test_config_field_spec_registry_contract() -> None:
    from core.services.scheduler.config.config_field_spec import (
        choice_label_map_for,
        choices_for,
        default_for,
        field_label_for,
        list_config_fields,
        page_metadata_for,
    )

    fields = {spec.key for spec in list_config_fields()}
    assert "sort_strategy" in fields
    assert "objective" in fields
    assert "freeze_window_days" in fields
    assert "auto_assign_persist" in fields
    objective_spec = next(spec for spec in list_config_fields() if spec.key == "objective")
    assert not hasattr(objective_spec, "policy")

    assert default_for("auto_assign_persist") == "yes"
    assert choices_for("objective") == (
        "min_overdue",
        "min_tardiness",
        "min_weighted_tardiness",
        "min_changeover",
    )
    assert choice_label_map_for("objective") == objective_choice_labels()
    assert choice_label_map_for("objective")["min_overdue"] == "最少超期"
    assert choice_label_map_for("objective")["min_weighted_tardiness"] == "最少加权拖期小时"
    assert field_label_for("holiday_default_efficiency") == "假期工作效率"
    assert field_label_for("preset_name") == "方案名称"

    metadata = page_metadata_for(
        [
            "algo_mode",
            "objective",
            "dispatch_mode",
            "dispatch_rule",
            "freeze_window_enabled",
            "freeze_window_days",
        ]
    )
    assert isinstance(metadata, dict)
    assert set(metadata.keys()) == {
        "algo_mode",
        "objective",
        "dispatch_mode",
        "dispatch_rule",
        "freeze_window_enabled",
        "freeze_window_days",
    }
    assert metadata["objective"].choices[0]["value"] == "min_overdue"
    assert metadata["objective"].choices[0]["label"] == "最少超期"
    assert metadata["freeze_window_enabled"].label == "锁定近期排程"
    assert metadata["freeze_window_days"].unit == "天"


def test_config_service_snapshot_includes_hidden_field_and_get_stays_single_arg(config_service: ConfigService) -> None:
    config_service.ensure_defaults()

    snap = config_service.get_snapshot()
    assert snap.auto_assign_persist == "yes"
    assert snap.to_dict()["auto_assign_persist"] == "yes"
    assert config_service.get("objective") == "min_overdue"
    with pytest.raises(TypeError):
        config_service.get("objective", "fallback")


def test_schedule_config_snapshot_hidden_field_defaults_to_yes() -> None:
    snap = ScheduleConfigSnapshot(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=0.8,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )

    assert snap.auto_assign_persist == "yes"
    assert snap.to_dict()["auto_assign_persist"] == "yes"


def test_build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_schedule_config_snapshot(_EmptyRepo(), strict_mode=True)

    assert exc_info.value.field == "sort_strategy"


def test_ensure_schedule_config_snapshot_strict_mode_rejects_missing_runtime_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ensure_schedule_config_snapshot({}, strict_mode=True, source="regression.strict_missing")

    assert exc_info.value.field == "sort_strategy"


def test_config_helpers_reject_removed_valid_override_kwargs() -> None:
    base = ScheduleConfigSnapshot(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=0.8,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )

    with pytest.raises(TypeError):
        build_schedule_config_snapshot(_EmptyRepo(), valid_strategies=("fifo",))

    with pytest.raises(TypeError):
        normalize_preset_snapshot({}, base=base, valid_strategies=("fifo",))
