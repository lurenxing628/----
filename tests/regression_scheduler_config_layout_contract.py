from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_config_separates_preset_actions_from_runtime_state() -> None:
    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)

        assert "aps-settings-action-grid" in source
        assert "aps-danger-zone" in source
        assert "当前配置状态" in source
        assert source.index("常用方案") < source.index("当前配置状态") < source.index("排产策略配置")
        assert "current_config_display_items" in source
        assert "current_config_notice_items" in source
        assert "current_config_summary_items" not in source
        assert "current_auto_assign_persist_item" not in source
        assert "current_config_state.status_label" not in source
        assert "current_config_state.repair_notices" not in source
        assert "auto_assign_persist_state.description" not in source
        assert "auto_assign_persist_state.label" not in source
        form_start = source.index("<h3 class=\"section-title\">排产策略配置</h3>")
        form_end = source.index('<div class="scheduler-config-form-grid">', form_start)
        form_intro = source[form_start:form_end]
        assert "config_degraded_fields" not in form_intro
        assert "config_hidden_warnings" not in form_intro
        assert "flash-card flash-warning scheduler-config-degraded-summary" not in form_intro

        assert 'name="preset_name"' in source
        assert 'name="next"' in source
        assert 'data-auto-submit="1"' in source
        assert 'data-autosave="true"' in source
        assert 'data-autosave-key="scheduler-config-main"' in source
        assert "scheduler-config-section--graph" in source
        assert "scheduler-config-mode-guide" in source
        assert "scheduler-config-field--wide" in source
        assert "scheduler-config-form-grid--graph" in source
        assert "scheduler-config-switches-heading" in source
        assert "选择“只看分析报告”时，系统只检查工序之间的先后关系" not in source

        assert 'name="ready_weight"' not in source
        assert 'name="auto_assign_persist"' not in source


def test_scheduler_config_setting_switches_use_compact_toggle_controls() -> None:
    setting_fields = (
        "freeze_window_enabled",
        "prefer_primary_skill",
        "enforce_ready_default",
        "auto_assign_enabled",
        "ortools_enabled",
        "graph_block_on_cycle",
        "graph_debug_export",
    )
    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)
        assert '{% include "scheduler/_config_switches.html" %}' in source
        switch_block = _read("templates/scheduler/_config_switches.html")
        macro_source = _read("templates/components/ui_macros.html")

        assert switch_block.count("scheduler-config-switch") >= len(setting_fields)
        assert switch_block.count("ui.toggle(") == len(setting_fields)
        assert "ui.toggle_row(" not in switch_block
        assert "aps-toggle-control" in macro_source
        assert "aps-toggle-input" in macro_source
        assert "aps-toggle-track" in macro_source
        assert "aps-toggle-thumb" in macro_source
        assert "aps-toggle-text" in macro_source
        assert 'label class="scheduler-config-switch-main"' not in switch_block

        for field_name in setting_fields:
            assert f'scheduler_config_toggles["{field_name}"]' in switch_block
        assert "type=\"checkbox\"" in macro_source
        assert "type=\"hidden\"" in macro_source
        assert macro_source.index('type="checkbox"') < macro_source.index('type="hidden"')


def main() -> None:
    test_scheduler_config_separates_preset_actions_from_runtime_state()
    test_scheduler_config_setting_switches_use_compact_toggle_controls()
    print("OK")


if __name__ == "__main__":
    main()
