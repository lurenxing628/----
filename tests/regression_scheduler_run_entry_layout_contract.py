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
        assert "aps-scheduler-filter-grid" in source

        run_panel_start = source.index('<div class="aps-run-panel">')
        table_start = source.index('id="batchesTable"')
        run_panel = source[run_panel_start:table_start]
        run_grid_start = run_panel.index("aps-run-panel-grid")
        run_grid_end = run_panel.index("aps-run-panel-actions", run_grid_start)
        run_grid = run_panel[run_grid_start:run_grid_end]
        for field_name in ("start_dt", "end_date", "enforce_ready", "strict_mode"):
            assert f'name="{field_name}"' in run_grid

        for marker in (
            'name="batch_ids"',
            'class="js-batch-check"',
            'class="js-select-all"',
            'id="jsSelectedCount"',
            'name="start_dt"',
            'name="end_date"',
            'name="enforce_ready"',
            'name="strict_mode"',
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


def main() -> None:
    test_scheduler_run_entry_is_visible_before_batch_table()
    test_scheduler_sub_pages_have_run_schedule_entry()
    test_run_panel_container_breakpoint_has_room_for_declared_columns()
    print("OK")


if __name__ == "__main__":
    main()
