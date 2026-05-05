from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_run_entry_is_visible_before_batch_table() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        assert 'id="jsRunScheduleForm"' in source
        assert "aps-run-panel" in source
        assert "aps-run-panel-grid" in source
        assert "排产操作" in source
        assert source.index("排产操作") < source.index('id="batchesTable"')
        assert "先勾选下方待排批次，再执行排产。" in source
        assert "aps-filter-bar" not in source
        assert "aps-query-form-grid" in source

        run_panel_start = source.index('<div class="aps-run-panel">')
        table_start = source.index('id="batchesTable"')
        run_panel = source[run_panel_start:table_start]
        run_grid_start = run_panel.index("aps-run-panel-grid")
        run_grid_end = run_panel.index("aps-run-panel-help", run_grid_start)
        run_grid = run_panel[run_grid_start:run_grid_end]
        assert 'name="start_dt"' in run_grid
        assert 'name="end_date"' in run_grid
        assert "'enforce_ready'" in run_grid
        assert "'strict_mode'" in run_grid
        assert "派工方式、智能派工策略、自动分配设备人员" not in run_grid
        assert "aps-run-panel-status" in run_panel
        assert "aps-run-options" in run_panel
        assert "aps-run-options-title" in run_panel
        assert run_panel.count("ui.toggle_row(") == 2
        assert run_panel.count("class='aps-run-option-row'") == 2
        assert "aps-choice-list aps-run-panel-options" not in run_panel
        assert 'class="aps-choice"' not in run_panel
        assert "aps-settings-toggle-control aps-settings-toggle-control-icon" not in run_panel
        assert "启用齐套约束（未齐套禁止排产）" not in run_panel
        assert "未齐套批次不进入排产。" in run_panel
        assert "配置不合法时直接停下" in run_panel
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
            "'enforce_ready'",
            "'strict_mode'",
            "scheduler.run_schedule",
            "scheduler.simulate_schedule",
        ):
            assert marker in source


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
    assert "minmax(240px, 1fr)" in css
    assert "minmax(190px, 0.8fr)" in css
    assert "minmax(230px, 1fr)" in css
    assert "@container (min-width: 760px) and (max-width: 1039px)" in css
    assert "grid-column: 1 / -1" in css


def test_latest_schedule_snapshot_uses_dedicated_sections() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        block = source[source.index('class="card aps-latest-schedule-card"') : source.index("批次列表")]
        assert "aps-latest-schedule-card" in block
        assert "aps-latest-schedule-head" in block
        assert "aps-latest-schedule-meta" in block
        assert "aps-latest-schedule-metrics" in block
        assert "aps-latest-schedule-status" in block
        assert "latest_notice_items" in block
        assert "ui.notice(item.title, item.body" in block
        assert "ui.summary_item_block('错误摘要'" in block
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
