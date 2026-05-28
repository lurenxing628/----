from __future__ import annotations

from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _table_block(source: str, marker: str) -> str:
    start = source.index(marker)
    return source[start : source.index("</table>", start)]


def _css_block(source: str, selector: str) -> str:
    start = source.index(selector)
    return source[start : source.index("}", start) + 1]


def test_materials_table_uses_editable_table_protection() -> None:
    source = _read("templates/material/materials.html")
    table_start = source.index('id="materialsTable"')
    previous_table_end = source.rfind("</table>", 0, table_start)
    wrapper_start = source.rfind("aps-table-scroll", 0, table_start)
    assert wrapper_start > previous_table_end

    table_block = _table_block(source, 'id="materialsTable"')
    for token in (
        "aps-table",
        "aps-table--fixed",
        "aps-table--editable",
        "aps-table--actions-nowrap",
        "aps-table-size-wide",
        'data-col-resize="1"',
        'data-table-key="v2_materialsTable"',
        "data-default-w",
        "data-min-w",
    ):
        assert token in table_block

    css = _read("static/css/ui_contract.css")
    editable_block = _css_block(css, ".aps-table--editable input,")
    for token in ("width: 100%;", "min-width: 0;", "max-width: 100%;", "box-sizing: border-box;"):
        assert token in editable_block


def test_resource_dispatch_resource_labels_keep_full_text_path() -> None:
    source = _read("static/js/resource_dispatch.js")

    helper_start = source.index("function fullTextCell")
    helper_block = source[helper_start : source.index("function renderFlags", helper_start)]
    assert 'title="' in helper_block
    assert 'data-full-text="' in helper_block
    assert "escapeHtml(v)" in helper_block

    rows_start = source.index("function buildDetailRowsHtml")
    rows_block = source[rows_start : source.index("function renderDetailRows", rows_start)]
    assert 'resourceCell(row, "current_resource", "aps-resource-cell", "")' in rows_block
    assert 'resourceCell(row, "counterpart_resource", "aps-resource-cell", "")' in rows_block
    assert "affectedResourceCell(row)" in rows_block
    assert "'<td>' + escapeHtml(row.current_resource_label || \"\") + '</td>'" not in rows_block
    assert "'<td>' + escapeHtml(row.counterpart_resource_label || \"\") + '</td>'" not in rows_block

    popup_start = source.index("function ganttPopup")
    popup_block = source[popup_start : source.index("function installResourceGanttPopupAutoFit", popup_start)]
    assert "affectedResourcePopupHtml(meta)" in popup_block
    assert "escapeHtml(affectedResourceSummary(meta))" not in popup_block


def test_fixed_table_rules_keep_scroll_or_readability_escape_hatches() -> None:
    css = _read("static/css/ui_contract.css")

    fixed_block = _css_block(css, ".aps-table--fixed th,")
    for token in ("overflow: hidden;", "text-overflow: ellipsis;", "white-space: nowrap;"):
        assert token in fixed_block

    multiline_block = _css_block(css, ".aps-table--multiline th,")
    for token in ("overflow: visible;", "text-overflow: clip;", "white-space: normal;", "overflow-wrap: anywhere;"):
        assert token in multiline_block

    overflow_guard = _read("tests/regression_ui_contract_table_overflow_guard.py")
    assert "aps-table-scroll" in overflow_guard
    assert "data-table-key" in overflow_guard
    assert "data-col-resize" in overflow_guard


def test_resource_dispatch_calendar_table_keeps_scroll_and_table_key_contract() -> None:
    template_source = _read("templates/scheduler/resource_dispatch.html")
    script_source = _read("static/js/resource_dispatch.js")
    css_source = _read("static/css/ui_contract.css")

    calendar_panel = template_source[
        template_source.index('id="rdCalendarPanel"') : template_source.index('id="rdGanttPanel"')
    ]
    assert 'class="aps-table-scroll" id="rdCalendarWrap"' in calendar_panel

    assert 'id="rdCalendarTable"' in script_source
    assert "table-layout-fixed" in script_source
    assert "aps-table-xwide" in script_source
    assert "table-sticky-col" in script_source
    assert "aps-resource-calendar-table" in script_source
    assert 'data-col-resize="1"' in script_source
    assert 'data-table-key="v1_resourceDispatchCalendar"' in script_source
    assert "data-default-w" in script_source
    assert "data-min-w" in script_source
    assert "aps-calendar-task" in script_source
    assert "aps-calendar-task--overdue" in script_source
    assert 'badge("超期", "error")' in script_source
    assert "calendarTaskField(\"批次\"" in script_source
    assert "calendarTaskField(\"工序\"" in script_source
    assert "calendarTaskFieldHtml(\"计划设备\"" in script_source
    assert "calendarTaskFieldHtml(\"计划人员\"" in script_source
    assert "calendarTaskField(\"图号 / 物料\"" in script_source
    assert "编号：" in script_source
    assert "完整身份：" not in script_source[script_source.index("function namedResourceInfo") : script_source.index("function renderFlags")]
    assert ".aps-calendar-task + .aps-calendar-task" in css_source
    assert 'html[data-theme="dark"] .aps-calendar-task' in css_source


def test_truncate_cell_helpers_are_not_used_by_active_templates_or_js() -> None:
    active_suffixes = (".html", ".js")
    offenders: List[str] = []
    for root in ("templates", "web_new_test/templates", "static/js"):
        for path in (REPO_ROOT / root).rglob("*"):
            if path.is_file() and path.suffix in active_suffixes:
                rel_path = path.relative_to(REPO_ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                if "truncate-cell" in source or "truncate-cell-150" in source:
                    offenders.append(rel_path)
    assert offenders == []


def main() -> None:
    test_materials_table_uses_editable_table_protection()
    test_resource_dispatch_resource_labels_keep_full_text_path()
    test_fixed_table_rules_keep_scroll_or_readability_escape_hatches()
    test_resource_dispatch_calendar_table_keeps_scroll_and_table_key_contract()
    test_truncate_cell_helpers_are_not_used_by_active_templates_or_js()
    print("OK")


if __name__ == "__main__":
    main()
