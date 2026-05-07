from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_run_entry_is_visible_before_batch_table() -> None:
    run_panel = _read("templates/scheduler/_run_panel.html")
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        combined_source = source + run_panel
        assert 'id="jsRunScheduleForm"' in source
        assert '{% include "scheduler/_run_panel.html" %}' in source
        assert source.index('{% include "scheduler/_run_panel.html" %}') < source.index('id="batchesTable"')
        assert "aps-run-panel" in run_panel
        assert "aps-run-panel-grid" in run_panel
        assert "排产操作" in run_panel
        assert "先勾选下方待排批次，再执行排产。" in run_panel
        assert "aps-filter-bar" not in source
        assert "aps-query-form-grid" in source

        run_grid_start = run_panel.index("aps-run-panel-grid")
        run_grid_end = run_panel.index("aps-run-panel-help", run_grid_start)
        run_grid = run_panel[run_grid_start:run_grid_end]
        assert 'name="start_dt"' in run_grid
        assert 'name="end_date"' in run_grid
        assert "run_options" in run_grid
        assert "ui.toggle(option.toggle" in run_grid
        assert "派工方式、智能派工策略、自动分配设备人员" not in run_grid
        assert "aps-run-panel-status" in run_panel
        assert "aps-run-options" in run_panel
        assert "aps-run-options-title" in run_panel
        assert "ui.toggle_row(" not in run_panel
        assert "class='aps-run-option-row'" in run_panel
        assert "aps-run-option-note" in run_panel
        assert "{% if option.note %}" in run_panel
        assert "aps-choice-list aps-run-panel-options" not in run_panel
        assert 'class="aps-choice"' not in run_panel
        assert "aps-settings-toggle-control aps-settings-toggle-control-icon" not in run_panel
        assert "启用齐套约束（未齐套禁止排产）" not in run_panel
        assert "aps-run-panel-help" in run_panel
        assert "ui.help_details" in run_panel
        assert "查看“发现参数问题就停止排产”的说明" in run_panel

        for marker in (
            'name="batch_ids"',
            'class="js-batch-check"',
            'class="js-select-all"',
            'id="jsSelectedCount"',
            'name="start_dt"',
            'name="end_date"',
            "scheduler.run_schedule",
            "scheduler.simulate_schedule",
        ):
            assert marker in combined_source

        vm_source = _read("web/viewmodels/scheduler_run_options.py")
        for marker in (
            '"runEnforceReady"',
            '"runStrictMode"',
            '"enforce_ready"',
            '"strict_mode"',
            "UiRunOption",
            "默认不启用。启用后，未齐套批次不进入排产，齐套日期作为最早开工日。",
            "配置不合法时直接停下",
        ):
            assert marker in vm_source


def test_scheduler_sub_pages_have_run_schedule_entry() -> None:
    for rel_path in (
        "templates/scheduler/config.html",
        "web_new_test/templates/scheduler/config.html",
        "templates/scheduler/calendar.html",
        "templates/scheduler/gantt.html",
        "web_new_test/templates/scheduler/gantt.html",
        "templates/scheduler/week_plan.html",
        "templates/scheduler/resource_dispatch.html",
        "templates/scheduler/analysis.html",
    ):
        source = _read(rel_path)
        assert "去执行排产" in source, f"{rel_path} 缺少回到执行排产的入口"
        assert "scheduler.batches_page" in source


def test_run_panel_container_breakpoint_has_room_for_declared_columns() -> None:
    css = _read("static/css/ui_contract.css")
    assert "@container (min-width: 1040px)" in css
    assert ".aps-run-panel-grid" in css
    assert ".aps-run-panel-help" in css
    assert ".aps-run-panel-status" in css
    assert ".aps-run-options" in css
    assert ".aps-run-option-row" in css
    assert ".aps-run-option-title" in css
    assert ".aps-run-option-desc" in css
    run_option_start = css.index(".aps-run-option-row {")
    run_option_block = css[run_option_start : css.index(".aps-run-option-row + .aps-run-option-row", run_option_start)]
    assert "width: 100%;" in run_option_block
    assert "flex-wrap: nowrap;" in run_option_block
    assert ".aps-run-option-row .aps-toggle-copy" in css
    assert ".aps-run-option-note:empty" in css
    assert "minmax(240px, 1fr)" in css
    assert "minmax(190px, 0.8fr)" in css
    assert "minmax(230px, 1fr)" in css
    assert "@container (min-width: 760px) and (max-width: 1039px)" in css
    medium_start = css.index("@container (min-width: 760px) and (max-width: 1039px)")
    medium_block = css[medium_start : css.index("@media (max-width: 1180px)", medium_start)]
    assert "grid-column: 1 / -1" in medium_block
    assert "repeat(2, minmax(0, 1fr))" not in medium_block


def test_latest_schedule_snapshot_uses_dedicated_sections() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        assert source.index("批次列表") < source.index('class="card aps-latest-schedule-card"')
        block = source[source.index('class="card aps-latest-schedule-card"') :]
        assert "aps-latest-schedule-card" in block
        assert "aps-latest-schedule-head" in block
        assert "aps-latest-schedule-meta" in block
        assert "aps-latest-schedule-metrics" in block
        assert "aps-latest-schedule-status" in block
        assert "latest_notice_items" in block
        assert "latest_detail_notice_items" in block
        assert "ui.notice(item.title, item.body" in block
        assert "ui.details_notice(notice, class='mt-2 scheduler-run-degraded-summary')" in block
        assert "ui.summary_item_block('错误摘要'" in block
        assert "ui.empty_state('还没有排过产'" in block
        assert "保存系统补齐的设备和人员" not in block
        assert "保存补齐资源" in block
        assert "查看说明" in block


def test_scheduler_error_summaries_render_as_summary_cards() -> None:
    cases = (
        ("templates/scheduler/analysis.html", "selected_summary_display.error_total"),
        ("templates/scheduler/week_plan.html", "selected_summary_display.error_total"),
        ("templates/scheduler/batches.html", "latest_summary_display.error_total"),
        ("web_new_test/templates/scheduler/batches.html", "latest_summary_display.error_total"),
        ("templates/system/history.html", "selected_summary_display.error_total"),
    )
    for rel_path, marker in cases:
        source = _read(rel_path)
        start = source.index(marker)
        block = source[start : source.index("{% endif %}", start)]
        assert "aps-summary-grid mt-2 aps-summary-health-grid" in block
        assert "ui.summary_item_block('错误摘要'" in block
        assert "'danger'" in block
        assert "ui.flash_details('查看前 '" in block
        assert "<div>错误摘要：" not in block
        assert "flash-card flash-warning mt-2" not in block


def main() -> None:
    test_scheduler_run_entry_is_visible_before_batch_table()
    test_scheduler_sub_pages_have_run_schedule_entry()
    test_run_panel_container_breakpoint_has_room_for_declared_columns()
    test_latest_schedule_snapshot_uses_dedicated_sections()
    test_scheduler_error_summaries_render_as_summary_cards()
    print("OK")


if __name__ == "__main__":
    main()
