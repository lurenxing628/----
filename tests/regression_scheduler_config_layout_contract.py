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

        assert 'name="preset_name"' in source
        assert 'name="next"' in source
        assert 'data-auto-submit="1"' in source
        assert 'data-autosave="true"' in source
        assert 'data-autosave-key="scheduler-config-main"' in source

        assert 'name="ready_weight"' not in source
        assert 'name="auto_assign_persist"' not in source


def test_scheduler_config_setting_switches_use_compact_toggle_controls() -> None:
    setting_fields = (
        "freeze_window_enabled",
        "prefer_primary_skill",
        "enforce_ready_default",
        "auto_assign_enabled",
        "ortools_enabled",
    )
    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)
        switch_start = source.index('<div class="scheduler-config-switches">')
        switch_end = source.index('<div class="mt-3">', switch_start)
        switch_block = source[switch_start:switch_end]

        assert switch_block.count("scheduler-config-switch") >= len(setting_fields)
        assert switch_block.count("aps-settings-toggle-control") == len(setting_fields)
        assert switch_block.count("aps-settings-toggle-input") == len(setting_fields)
        assert switch_block.count("aps-settings-toggle-track") == len(setting_fields)
        assert switch_block.count("aps-settings-toggle-thumb") == len(setting_fields)
        assert switch_block.count("aps-settings-toggle-text") == len(setting_fields)
        assert 'label class="scheduler-config-switch-main"' not in switch_block

        for field_name in setting_fields:
            assert f'name="{field_name}" value="yes"' in switch_block
            assert f'type="hidden" name="{field_name}" value="no"' in switch_block


def main() -> None:
    test_scheduler_config_separates_preset_actions_from_runtime_state()
    test_scheduler_config_setting_switches_use_compact_toggle_controls()
    print("OK")


if __name__ == "__main__":
    main()
