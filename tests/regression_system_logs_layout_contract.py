from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_system_logs_uses_separate_cards_and_stable_filter_grid() -> None:
    source = _read("templates/system/logs.html")

    assert "inline-flex-wrap" not in source
    assert "日志自动清理设置" in source
    assert "筛选日志" in source
    assert "aps-settings-layout-card" in source
    assert "aps-settings-cleanup-grid" in source
    assert "aps-filter-grid" in source

    hero_start = source.index('<div class="card aps-page-hero">')
    hero_end = source.index("日志自动清理设置", hero_start)
    hero = source[hero_start:hero_end]
    for forbidden in ("日志自动清理设置", "筛选日志", "logsBatchDeleteForm"):
        assert forbidden not in hero

    for field_name in (
        "start_time",
        "end_time",
        "module",
        "action",
        "log_level",
        "limit",
        "auto_log_cleanup_keep_days",
        "auto_log_cleanup_interval_minutes",
    ):
        assert f'name="{field_name}"' in source
    assert "ui.toggle(page.cleanup_toggle" in source
    assert '"auto_log_cleanup_enabled"' in _read("web/viewmodels/system_logs_vm.py")

    cleanup_start = source.index("日志自动清理设置")
    cleanup_end = source.index("筛选日志", cleanup_start)
    cleanup_block = source[cleanup_start:cleanup_end]
    assert cleanup_block.count("有人打开或操作页面时") == 1
    assert "aps-settings-cleanup-actions" in cleanup_block
    assert "ui.toggle(page.cleanup_toggle" in cleanup_block
    assert "page.cleanup_toggle" in cleanup_block
    assert cleanup_block.count("aps-settings-switch") == 0
    assert "启用自动清理日志" not in cleanup_block
    assert "按保留天数清理旧日志" not in cleanup_block
    assert "自动清理" in cleanup_block
    assert "aps-empty-state" in _read("templates/components/ui_macros.html")
    assert 'label class="muted"' not in cleanup_block
    for marker in (
        "aps-settings-enable-field",
        "aps-settings-keep-days",
        "aps-settings-interval",
        "aps-settings-last-run",
    ):
        assert marker in cleanup_block

    css = _read("static/css/ui_contract.css")
    assert ".aps-settings-layout-card" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));" in css
    assert "@container (min-width: 760px)" in css
    assert ".aps-settings-switch" in css
    assert ".aps-settings-switch-title" in css
    assert ".aps-settings-switch-desc" in css
    assert ".aps-toggle-control" in css
    assert ".aps-toggle-track" in css
    assert ".aps-toggle-row" in css
    assert ".aps-toggle-title" in css
    assert ".aps-toggle-desc" in css
    assert ".aps-toggle-input:checked + .aps-toggle-track" in css
    assert ".form-field .aps-toggle-control" in css
    assert ".form-field .aps-toggle-title" in css
    assert ".form-field .aps-toggle-desc" in css
    assert "minmax(118px, max-content)" in css
    assert "justify-self: start;" in css
    assert "grid-column: 1;" in css
    assert "#systemLogsTable td" not in css
    assert ".aps-table--multiline th" in css
    assert ".aps-table--multiline td" in css
    assert ".aps-table--actions-nowrap .table-actions" in css
    assert "overflow: visible;" in css
    assert "white-space: normal;" in css

    result_start = source.index("查询结果")
    assert source.index('id="logsBatchDeleteForm"') > result_start
    assert 'name="log_ids"' in source
    assert 'form="logsBatchDeleteForm"' in source
    result_block = source[result_start:]
    assert '<input type="checkbox" class="js-log-select-all"' in result_block
    assert "<summary>排查信息</summary>" in result_block
    assert "aps-table--multiline" in result_block
    assert "aps-table--actions-nowrap" in result_block


def test_system_backup_auto_job_switches_use_readable_setting_rows() -> None:
    source = _read("templates/system/backup.html")
    settings_start = source.index("自动备份与自动清理")
    settings_end = source.index("扩展功能状态", settings_start)
    settings_block = source[settings_start:settings_end]

    assert settings_block.count("aps-settings-toggle-row") == 2
    assert settings_block.count("ui.toggle(page.auto_backup") == 2
    assert settings_block.count("aps-settings-switch aps-settings-switch-compact") == 0
    assert settings_block.count("aps-settings-switch") == 0
    for field_name, title, desc in (
        ("auto_backup_enabled", "自动备份", "生成退出备份"),
        ("auto_backup_cleanup_enabled", "自动清理备份", "清理旧备份"),
    ):
        assert field_name in _read("web/viewmodels/system_backup_page.py")
        assert title in _read("web/viewmodels/system_backup_page.py")
        assert desc in _read("web/viewmodels/system_backup_page.py")
    assert "d-inline-block" not in settings_block

    plugin_block = source[source.index("扩展功能状态") :]
    assert "aps-plugin-status-summary" in plugin_block
    assert "ui.summary_grid(page.plugin_summary_items" in plugin_block
    assert '<div class="muted mt-2">\n        加载时间' not in plugin_block
    assert "加载时间：{{ plugin_status.loaded_at or '-' }}<br/>" not in plugin_block
    assert "plugin_config_source_label" not in plugin_block
    assert "plugin_telemetry_label" not in plugin_block
    assert 'id="pluginStatusTable"' in plugin_block
    assert 'name="enabled"' in plugin_block
    assert "system.plugin_toggle" in plugin_block
    assert "aps-table-toggle-row" not in plugin_block
    assert 'label class="muted"' in plugin_block
    assert '<input type="checkbox" name="enabled"' in plugin_block

    css = _read("static/css/ui_contract.css")
    readonly_dark_start = css.index('html[data-theme="dark"] .readonly-value')
    readonly_dark_block = css[readonly_dark_start : css.index("}", readonly_dark_start)]
    assert "background: var(--ui-card-bg, #1e293b);" in readonly_dark_block
    assert "border-color: var(--ui-border, #334155);" in readonly_dark_block
    assert "color: var(--ui-text, #f1f5f9);" in readonly_dark_block


def main() -> None:
    test_system_logs_uses_separate_cards_and_stable_filter_grid()
    test_system_backup_auto_job_switches_use_readable_setting_rows()
    print("OK")


if __name__ == "__main__":
    main()
