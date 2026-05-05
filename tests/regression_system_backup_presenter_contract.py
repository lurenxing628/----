from __future__ import annotations

import pytest

from web.viewmodels.system_backup_page import (
    PLUGIN_CONFIG_SOURCE_LABELS,
    PLUGIN_ENABLED_SOURCE_LABELS,
    PLUGIN_TELEMETRY_STATES,
    build_plugin_status_rows,
    build_plugin_summary_items,
    build_system_backup_page_view_model,
)


def _settings(**overrides):
    data = {
        "auto_backup_enabled": "yes",
        "auto_backup_cleanup_enabled": "no",
    }
    data.update(overrides)
    return data


def _plugin_status(**overrides):
    data = {
        "loaded_at": "2026-05-05 10:00:00",
        "config_source": "config",
        "telemetry_persisted": True,
        "degraded": False,
        "degradation_events": [],
        "conflicted_capabilities": [],
        "registry": {"capabilities": ["demo.capability"]},
        "statuses": [
            {
                "plugin_id": "demo_plugin",
                "name": "演示扩展",
                "version": "1.0",
                "enabled": "yes",
                "loaded": "no",
                "enabled_source": "config",
                "error": "",
                "capabilities": ["demo.capability"],
            }
        ],
    }
    data.update(overrides)
    return data


def test_plugin_config_source_labels_cover_declared_sources() -> None:
    assert PLUGIN_CONFIG_SOURCE_LABELS == {
        "config": "全部来自系统配置",
        "mixed": "部分来自系统配置，部分按默认开关运行",
        "default_due_to_db_unavailable": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
        "default_due_to_config_reader_failed": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
        "default_due_to_config_read_failed": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
        "default": "当前按默认开关运行",
    }


def test_plugin_summary_items_reject_unknown_config_source() -> None:
    status = _plugin_status(config_source="future_source")

    with pytest.raises(KeyError):
        build_plugin_summary_items(status)


def test_plugin_summary_items_reject_unknown_telemetry_state() -> None:
    status = _plugin_status(telemetry_persisted="yes")

    with pytest.raises(KeyError):
        build_plugin_summary_items(status)


def test_plugin_summary_items_use_strict_labels_and_tones() -> None:
    status = _plugin_status(config_source="mixed", telemetry_persisted=False, degraded=True, degradation_events=[{}])
    items = build_plugin_summary_items(status)
    by_label = {item.label: item for item in items}

    assert by_label["配置来源"].value == PLUGIN_CONFIG_SOURCE_LABELS["mixed"]
    assert by_label["留痕状态"].value == PLUGIN_TELEMETRY_STATES[False][0]
    assert by_label["留痕状态"].tone == PLUGIN_TELEMETRY_STATES[False][1]
    assert by_label["启动问题"].tone == "danger"


def test_plugin_status_rows_reject_unknown_enabled_source() -> None:
    status = _plugin_status(
        statuses=[
            {
                "plugin_id": "demo_plugin",
                "name": "演示扩展",
                "version": "1.0",
                "enabled": "yes",
                "loaded": "yes",
                "enabled_source": "future_source",
                "error": "",
                "capabilities": [],
            }
        ]
    )

    with pytest.raises(KeyError):
        build_plugin_status_rows(status)


def test_plugin_status_rows_reject_invalid_yes_no_states() -> None:
    status = _plugin_status(statuses=[dict(_plugin_status()["statuses"][0], loaded="maybe")])

    with pytest.raises(ValueError, match="plugin.loaded"):
        build_plugin_status_rows(status)


def test_plugin_status_rows_format_template_ready_fields() -> None:
    row = build_plugin_status_rows(_plugin_status())[0]

    assert row.plugin_id == "demo_plugin"
    assert row.enabled_checked_attr == "checked"
    assert row.loaded_label == "未加载"
    assert row.enabled_source_label == PLUGIN_ENABLED_SOURCE_LABELS["config"]
    assert row.capability_count == 1
    assert row.has_capabilities is True


def test_backup_toggle_rows_keep_checkbox_hidden_contract() -> None:
    page = build_system_backup_page_view_model(_settings(), _plugin_status())

    assert page.auto_backup_toggle.name == "auto_backup_enabled"
    assert page.auto_backup_toggle.checked_attr == "checked"
    assert page.auto_backup_toggle.hidden_value == "no"
    assert page.auto_backup_toggle.submitted_value == "no"
    assert page.auto_backup_cleanup_toggle.name == "auto_backup_cleanup_enabled"
    assert page.auto_backup_cleanup_toggle.checked_attr == ""
    assert page.auto_backup_cleanup_toggle.hidden_value == "no"
    assert page.auto_backup_cleanup_toggle.submitted_value == "no"
