from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_calendar_pages_use_shared_holiday_default_efficiency_helper() -> None:
    scheduler_route = _read("web/routes/domains/scheduler/scheduler_calendar_pages.py")
    personnel_route = _read("web/routes/personnel_calendar_pages.py")

    assert "def _resolve_page_holiday_default_efficiency" not in scheduler_route
    assert "def _resolve_page_holiday_default_efficiency" not in personnel_route
    assert "get_holiday_default_efficiency_display_state(" in scheduler_route
    assert "get_holiday_default_efficiency_display_state(" in personnel_route


def test_error_handlers_prefer_config_service_field_labels() -> None:
    from web.error_handlers import _resolve_field_label

    source = _read("web/error_handlers.py")

    assert "config_field_spec import field_label_for" not in source
    assert "get_user_visible_field_label(" in source
    assert _resolve_field_label({"field": "time_budget_seconds"}) == "计算时间上限"


def test_scheduler_config_page_requests_and_uses_visible_field_metadata() -> None:
    route_source = _read("web/routes/domains/scheduler/scheduler_config.py")
    display_state_source = _read("web/routes/domains/scheduler/scheduler_config_display_state.py")
    template_source = _read("templates/scheduler/config.html")

    assert "get_scheduler_visible_config_field_metadata" in route_source
    for field in (
        "sort_strategy",
        "priority_weight",
        "due_weight",
        "holiday_default_efficiency",
        "enforce_ready_default",
        "prefer_primary_skill",
        "dispatch_mode",
        "dispatch_rule",
        "auto_assign_enabled",
        "ortools_enabled",
        "ortools_time_limit_seconds",
        "algo_mode",
        "time_budget_seconds",
        "objective",
        "freeze_window_enabled",
        "freeze_window_days",
    ):
        assert f'"{field}"' in display_state_source

    for token in (
        "sort_strategy_meta.label",
        "priority_weight_meta.label",
        "due_weight_meta.label",
        "holiday_default_efficiency_meta.label",
        "enforce_ready_default_meta.label",
        "prefer_primary_skill_meta.label",
        "auto_assign_enabled_meta.label",
        "ortools_enabled_meta.label",
        "ortools_time_limit_seconds_meta.unit",
        "time_budget_seconds_meta.label",
    ):
        assert token in template_source


def test_scheduler_config_template_shows_shared_preset_degradation_notice() -> None:
    template_source = _read("templates/scheduler/config.html")

    for token in (
        "missing_preset_endpoints",
        "scheduler.preset_apply",
        "scheduler.preset_save",
        "scheduler.preset_delete",
        '<details class="debug-details muted">',
        "后端接口未注册（endpoint）",
        "logs/aps.log、logs/aps_error.log",
    ):
        assert token in template_source


def test_scheduler_config_template_surfaces_shared_degraded_field_warning_contract() -> None:
    route_source = _read("web/routes/domains/scheduler/scheduler_config.py")
    display_state_source = _read("web/routes/domains/scheduler/scheduler_config_display_state.py")
    template_source = _read("templates/scheduler/config.html")

    for token in (
        "config_field_warnings",
        "config_degraded_fields",
        "config_hidden_warnings",
        "build_config_degraded_display_state",
    ):
        assert token in route_source

    assert "build_auto_assign_persist_display_state" in display_state_source
    assert '"unknown"' in display_state_source
    for token in (
        "scheduler-config-degraded-summary",
        "scheduler-config-field-warning",
        "config_field_warnings.get(",
        "config_degraded_fields",
    ):
        assert token in template_source


def test_scheduler_config_v2_template_matches_shared_metadata_and_warning_contract() -> None:
    template_source = _read("web_new_test/templates/scheduler/config.html")

    for token in (
        "sort_strategy_meta.label",
        "priority_weight_meta.label",
        "due_weight_meta.label",
        "holiday_default_efficiency_meta.label",
        "prefer_primary_skill_meta.label",
        "auto_assign_enabled_meta.label",
        "ortools_enabled_meta.label",
        "ortools_time_limit_seconds_meta.unit",
        "time_budget_seconds_meta.label",
        "missing_preset_endpoints",
        "scheduler-config-degraded-summary",
        "scheduler-config-field-warning",
        "config_field_warnings.get(",
    ):
        assert token in template_source


def test_scheduler_manual_path_source_requires_base_dir_and_distinguishes_missing_reasons() -> None:
    route_source = _read("web/routes/domains/scheduler/scheduler_config.py")

    assert 'current_app.config.get("BASE_DIR")' in route_source
    assert "current_app.root_path" not in route_source
    assert "return None, []" in route_source
    assert route_source.count("if not candidates:") >= 2
    assert "manual_path, candidates = _resolve_scheduler_manual_md_path()" in route_source
    assert "candidates=%s" in route_source
