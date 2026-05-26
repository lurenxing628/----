from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_report_pages_use_stable_filter_grid_and_preserve_contracts() -> None:
    pages = (
        ("templates/reports/overdue.html", ("version", "scenario_id"), ("overdueTable",)),
        ("templates/reports/utilization.html", ("version", "scenario_id", "start_date", "end_date"), ("utilizationMachineTable", "utilizationOperatorTable")),
        ("templates/reports/downtime.html", ("version", "scenario_id", "start_date", "end_date"), ("downtimeTable",)),
    )
    for rel_path, field_names, table_ids in pages:
        source = _read(rel_path)
        assert "ui.aps_page_hero" in source
        assert "aps-report-filter-card" in source
        assert "aps-report-filter-grid" in source
        assert "aps-report-version-field" in source
        assert "aps-report-actions" in source
        assert "aps-filter-bar" not in source
        assert "aps-filter-note" in source
        assert "aps-result-summary-grid" in source
        assert "ui.version_option_label" in source
        assert "导出 Excel" in source
        assert "模拟预览暂不支持导出，请切换到正式采用方案" in source
        assert "正式计划还没有改变" in source
        for field_name in field_names:
            assert f'name="{field_name}"' in source
        for table_id in table_ids:
            assert f'id="{table_id}"' in source
            table_tag = re.search(rf'<table[^>]*id="{table_id}"[^>]*>', source)
            assert table_tag, f"{rel_path} 缺少 {table_id} 表格标签"
            assert 'data-col-resize="1"' in table_tag.group(0)
        assert "aps-table-scroll" in source
        if "start_date" in field_names:
            assert "aps-report-start-date" in source
            assert "aps-report-end-date" in source
            assert "aps-report-date-source" in source

    overdue = _read("templates/reports/overdue.html")
    assert "aps-report-filter-grid--single" in overdue
    assert "结果（总" not in overdue

    css = _read("static/css/ui_contract.css")
    assert ".aps-report-filter-card" in css
    assert "@container (min-width: 900px)" in css


def main() -> None:
    test_report_pages_use_stable_filter_grid_and_preserve_contracts()
    print("OK")


if __name__ == "__main__":
    main()
