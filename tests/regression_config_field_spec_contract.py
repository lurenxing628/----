"""回归测试：config_field_spec 字段注册表契约——list_config_fields/default_for/choices_for/choice_label_map_for/page_metadata_for 必须给出 graph_* 一族与 objective/dispatch 等字段的默认值、选项、中文标签与 hint 文案，且 ConfigService.get_page_metadata 与快照、隐藏字段 auto_assign_persist 默认 yes、strict 模式缺 sort_strategy 必须 ValidationError、被移除的 valid_strategies 等 kwargs 必须 TypeError。"""

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
            get_field_spec,
            list_config_fields,
            page_metadata_for,
        )

    field_keys = [spec.key for spec in list_config_fields()]
    fields = set(field_keys)
    assert "sort_strategy" in fields
    assert "objective" in fields
    assert "freeze_window_days" in fields
    assert "auto_assign_persist" in fields
    assert "graph_analysis_mode" in fields
    objective_spec = next(spec for spec in list_config_fields() if spec.key == "objective")
    assert "graph_analysis_mode" in fields
    assert "graph_block_on_cycle" in fields
    assert "graph_critical_weight" in fields
    assert "graph_impact_weight" in fields
    assert "graph_candidate_weight_count" in fields
    assert "graph_selection_policy" in fields
    assert "graph_overdue_tolerance_count" in fields
    assert "graph_tardiness_tolerance_ratio" in fields
    assert "graph_debug_export" in fields
    assert not hasattr(objective_spec, "policy")

    assert default_for("auto_assign_persist") == "yes"
    assert default_for("graph_analysis_mode") == "on"
    assert choices_for("graph_analysis_mode") == ("off", "report", "on")
    assert choice_label_map_for("graph_analysis_mode")["report"]
    assert default_for("graph_block_on_cycle") == "no"
    assert default_for("graph_critical_weight") == 500
    assert default_for("graph_impact_weight") == 10
    assert default_for("graph_candidate_weight_count") == 5
    assert choices_for("graph_candidate_weight_count") == ("3", "5", "7")
    assert default_for("graph_selection_policy") == "balanced"
    assert choices_for("graph_selection_policy") == ("balanced", "score_only")
    assert default_for("graph_overdue_tolerance_count") == 1
    assert choices_for("graph_overdue_tolerance_count") == ("0", "1", "2")
    assert default_for("graph_tardiness_tolerance_ratio") == 0.10
    assert choices_for("graph_tardiness_tolerance_ratio") == ("0.05", "0.1", "0.2")
    assert default_for("graph_debug_export") == "no"
    assert choices_for("objective") == (
        "min_overdue",
        "min_tardiness",
        "min_weighted_tardiness",
        "min_changeover",
    )
    assert choice_label_map_for("objective") == objective_choice_labels()
    assert choices_for("graph_analysis_mode") == ("off", "report", "on")
    assert default_for("graph_critical_weight") == 500
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
            "graph_analysis_mode",
            "graph_block_on_cycle",
            "graph_critical_weight",
            "graph_impact_weight",
            "graph_candidate_weight_count",
            "graph_selection_policy",
            "graph_overdue_tolerance_count",
            "graph_tardiness_tolerance_ratio",
            "graph_debug_export",
        ]
    )
    assert isinstance(metadata, dict)
    assert list(metadata.keys()) == [
        "algo_mode",
        "objective",
        "dispatch_mode",
        "dispatch_rule",
        "freeze_window_enabled",
        "freeze_window_days",
        "graph_analysis_mode",
        "graph_block_on_cycle",
        "graph_critical_weight",
        "graph_impact_weight",
        "graph_candidate_weight_count",
        "graph_selection_policy",
        "graph_overdue_tolerance_count",
        "graph_tardiness_tolerance_ratio",
        "graph_debug_export",
    ]
    assert set(metadata.keys()) == {
        "algo_mode",
        "objective",
        "dispatch_mode",
        "dispatch_rule",
        "freeze_window_enabled",
        "freeze_window_days",
        "graph_analysis_mode",
        "graph_block_on_cycle",
        "graph_critical_weight",
        "graph_impact_weight",
        "graph_candidate_weight_count",
        "graph_selection_policy",
        "graph_overdue_tolerance_count",
        "graph_tardiness_tolerance_ratio",
        "graph_debug_export",
    }
    assert metadata["objective"].choices[0]["value"] == "min_overdue"
    assert metadata["objective"].choices[2]["value"] == "min_weighted_tardiness"
    assert metadata["objective"].choices == tuple(
        {"value": key, "label": label} for key, label in objective_choice_labels().items()
    )
    assert metadata["dispatch_rule"].choices[2]["value"] == "atc"
    assert metadata["freeze_window_enabled"].label == "锁定近期排程"
    assert metadata["freeze_window_enabled"].hint
    assert metadata["freeze_window_days"].unit == "天"
    assert metadata["graph_analysis_mode"].choices[0]["value"] == "off"
    assert metadata["graph_analysis_mode"].choices[1]["value"] == "report"
    assert metadata["graph_analysis_mode"].choices[2]["value"] == "on"
    assert "参与排产" in metadata["graph_analysis_mode"].hint
    assert "先排普通方案" in metadata["graph_analysis_mode"].hint
    assert metadata["graph_candidate_weight_count"].label == "重点工序方案档数"
    assert metadata["graph_selection_policy"].label == "正式方案选择方式"
    assert metadata["graph_selection_policy"].choices[0]["value"] == "balanced"
    assert metadata["graph_overdue_tolerance_count"].choices[0]["value"] == "0"
    assert metadata["graph_tardiness_tolerance_ratio"].choices[1]["value"] == "0.1"
    assert metadata["graph_critical_weight"].label == "重点工序提前权重"
    assert "影响完工时间的工序会更靠前" in get_field_spec("graph_critical_weight").description
    assert "会影响更多后续工序的当前工序会更靠前" in get_field_spec("graph_impact_weight").description


def test_config_service_exposes_same_page_metadata_shape() -> None:
    service = object.__new__(ConfigService)

    metadata = service.get_page_metadata(
        [
            "algo_mode",
            "objective",
            "dispatch_mode",
            "dispatch_rule",
            "freeze_window_enabled",
            "freeze_window_days",
            "graph_analysis_mode",
            "graph_block_on_cycle",
            "graph_critical_weight",
            "graph_impact_weight",
            "graph_candidate_weight_count",
            "graph_selection_policy",
            "graph_overdue_tolerance_count",
            "graph_tardiness_tolerance_ratio",
            "graph_debug_export",
        ],
    )

    assert isinstance(metadata, dict)
    assert metadata["algo_mode"].label
    assert metadata["objective"].choices[0]["value"] == "min_overdue"
    assert metadata["objective"].choices[0]["label"] == "最少超期"
    assert metadata["graph_analysis_mode"].choices[1]["value"] == "report"
    assert metadata["graph_block_on_cycle"].label == "工序关系互相卡住时停止排产"


def test_config_service_snapshot_includes_hidden_field_and_get_stays_single_arg(config_service: ConfigService) -> None:
    config_service.ensure_defaults()

    snap = config_service.get_snapshot()
    assert snap.auto_assign_persist == "yes"
    assert snap.to_dict()["auto_assign_persist"] == "yes"
    assert snap.graph_analysis_mode == "on"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_critical_weight == 500
    assert snap.graph_impact_weight == 10
    assert snap.graph_candidate_weight_count == 5
    assert snap.graph_selection_policy == "balanced"
    assert snap.graph_overdue_tolerance_count == 1
    assert snap.graph_tardiness_tolerance_ratio == 0.10
    assert snap.graph_debug_export == "no"
    assert config_service.get("objective") == "min_overdue"
    assert snap.graph_analysis_mode == "on"
    assert snap.to_dict()["graph_critical_weight"] == 500
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
        graph_analysis_mode="off",
        graph_block_on_cycle="no",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_debug_export="no",
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
        graph_analysis_mode="off",
        graph_block_on_cycle="no",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_debug_export="no",
    )

    with pytest.raises(TypeError):
        build_schedule_config_snapshot(_EmptyRepo(), valid_strategies=("fifo",))

    with pytest.raises(TypeError):
        normalize_preset_snapshot({}, base=base, valid_strategies=("fifo",))
