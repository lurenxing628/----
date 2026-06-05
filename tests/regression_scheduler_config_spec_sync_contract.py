"""回归测试：排产配置的两套字段规格须始终同步——config_field_spec.list_config_fields() 与 schedule_config_runtime.list_runtime_config_fields() 的 key 集合、field_type/default/min_value/min_inclusive/choices 必须逐项一致，且九个 graph_* 配置字段在两套规格中均按既定契约注册。"""

from __future__ import annotations

from core.models.schedule_config_runtime import list_runtime_config_fields
from core.services.scheduler.config.config_field_spec import list_config_fields


def test_scheduler_config_spec_and_runtime_spec_stay_in_sync() -> None:
    service_specs = {spec.key: spec for spec in list_config_fields()}
    runtime_specs = {spec.key: spec for spec in list_runtime_config_fields()}

    assert list(runtime_specs) == list(service_specs)
    for key, service_spec in service_specs.items():
        runtime_spec = runtime_specs[key]
        assert runtime_spec.field_type == service_spec.field_type
        assert runtime_spec.default == service_spec.default
        assert runtime_spec.min_value == service_spec.min_value
        assert runtime_spec.min_inclusive == service_spec.min_inclusive
        assert runtime_spec.choices == service_spec.choices


def test_graph_config_fields_are_registered_in_both_specs() -> None:
    runtime_specs = {spec.key: spec for spec in list_runtime_config_fields()}
    service_specs = {spec.key: spec for spec in list_config_fields()}

    expected = {
        "graph_analysis_mode": ("enum", "on", None, True, ("off", "report", "on")),
        "graph_block_on_cycle": ("yes_no", "no", None, True, ("yes", "no")),
        "graph_critical_weight": ("int", 500, 0, True, ()),
        "graph_impact_weight": ("int", 10, 0, True, ()),
        "graph_candidate_weight_count": ("int", 5, None, True, ("3", "5", "7")),
        "graph_selection_policy": ("enum", "balanced", None, True, ("balanced", "score_only")),
        "graph_overdue_tolerance_count": ("int", 1, None, True, ("0", "1", "2")),
        "graph_tardiness_tolerance_ratio": ("float", 0.10, None, True, ("0.05", "0.1", "0.2")),
        "graph_debug_export": ("yes_no", "no", None, True, ("yes", "no")),
    }
    for key, contract in expected.items():
        assert key in service_specs
        assert key in runtime_specs
        for specs in (service_specs, runtime_specs):
            spec = specs[key]
            assert (
                spec.field_type,
                spec.default,
                spec.min_value,
                spec.min_inclusive,
                spec.choices,
            ) == contract
