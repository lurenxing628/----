from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _css_block(source: str, selector: str) -> str:
    start = source.index(selector)
    return source[start : source.index("}", start) + 1]


def _media_block(source: str, marker: str) -> str:
    start = source.index(marker)
    next_media = source.find("@media", start + len(marker))
    next_container = source.find("@container", start + len(marker))
    candidates = [pos for pos in (next_media, next_container) if pos >= 0]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def _class_tokens(attrs: List[Tuple[str, Optional[str]]]) -> Set[str]:
    for name, value in attrs:
        if name == "class" and value:
            return set(value.split())
    return set()


class _FloatingManualParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: List[Tuple[str, bool]] = []
        self._wrapper_depth: Optional[int] = None
        self.popover_inside_wrapper = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        classes = _class_tokens(attrs)
        is_wrapper = tag == "div" and {"floating-manual-wrapper", "no-print"}.issubset(classes)
        if is_wrapper:
            self._wrapper_depth = len(self._stack) + 1
        elif (
            tag == "div"
            and self._wrapper_depth is not None
            and len(self._stack) >= self._wrapper_depth
            and "manual-popover" in classes
        ):
            self.popover_inside_wrapper = True
        self._stack.append((tag, is_wrapper))

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        open_tag, is_wrapper = self._stack.pop()
        if open_tag == tag and is_wrapper:
            self._wrapper_depth = None


def _floating_manual_macro_block(source: str) -> str:
    start = source.index("{% macro floating_manual_button() %}")
    end = source.index("{% endmacro %}", start)
    return source[start:end]


def _popover_is_inside_floating_wrapper(source: str) -> bool:
    parser = _FloatingManualParser()
    parser.feed(_floating_manual_macro_block(source))
    return parser.popover_inside_wrapper


def test_excel_demo_current_people_table_has_scroll_and_readable_remark() -> None:
    source = _read("templates/excel/demo.html")
    key_start = source.index('data-table-key="v1_excelDemoCurrentPeople"')
    table_start = source.rfind("<table", 0, key_start)
    previous_table_end = source.rfind("</table>", 0, table_start)
    wrapper_start = source.rfind("aps-table-scroll", 0, table_start)
    assert wrapper_start > previous_table_end

    table_block = source[table_start : source.index("</table>", table_start)]
    for token in (
        "aps-table",
        "aps-table--fixed",
        "aps-table--multiline",
        "aps-table-size-compact",
        'data-col-resize="1"',
        'data-table-key="v1_excelDemoCurrentPeople"',
        'data-col-key="remark"',
        "data-default-w",
        "data-min-w",
        "aps-table-cell-note",
        'title="{{ r[\'备注\'] or \'\' }}"',
    ):
        assert token in table_block


def test_excel_action_buttons_have_small_screen_fallback() -> None:
    css = _read("static/css/ui_contract.css")
    desktop_block = _css_block(css, ".aps-excel-card-actions {")
    assert "display: grid;" in desktop_block
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in desktop_block

    button_block = _css_block(css, ".aps-excel-card-actions .btn {")
    assert "width: 100%;" in button_block
    assert "white-space: nowrap;" in button_block

    small_block = _media_block(css, "@media (max-width: 520px)")
    assert ".aps-excel-card-actions" in small_block
    assert "grid-template-columns: 1fr;" in small_block
    assert ".aps-excel-card-actions .btn" in small_block
    assert "white-space: normal;" in small_block


def test_action_and_run_status_wrap_on_small_screens() -> None:
    css = _read("static/css/ui_contract.css")

    action_status = _css_block(css, ".aps-action-card-status {")
    assert "margin-left: auto;" in action_status
    assert "white-space: nowrap;" in action_status

    run_status = _css_block(css, ".aps-run-panel-status {")
    assert "margin-left: auto;" in run_status
    assert "white-space: nowrap;" in run_status

    small_block = _media_block(css, "@media (max-width: 520px)")
    assert ".aps-action-card-status" in small_block
    assert ".aps-run-panel-status" in small_block
    assert "flex-basis: 100%;" in small_block
    assert "margin-left: 0;" in small_block
    assert "white-space: normal;" in small_block

    batches_manage = _read("templates/scheduler/batches_manage.html")
    actions_start = batches_manage.index("aps-action-card-actions")
    actions_block = batches_manage[actions_start : batches_manage.index("</div>", actions_start)]
    assert "aps-action-card-status" in actions_block
    assert "toolbar-actions-nowrap" not in actions_block


def test_floating_manual_button_is_fixed_outside_sidebar() -> None:
    css = _read("static/css/ui_contract.css")
    base_block = _css_block(css, ".floating-manual-wrapper {")
    assert "position: fixed;" in base_block
    assert "right: 24px;" in base_block
    assert "bottom: 24px;" in base_block

    sidebar_block = _css_block(css, ".sidebar .floating-manual-wrapper {")
    assert "position: relative;" in sidebar_block
    assert "right: auto;" in sidebar_block
    assert "bottom: auto;" in sidebar_block

    sidebar_popover_block = _css_block(css, ".sidebar .manual-popover {")
    assert "left: calc(100% + 12px);" in sidebar_popover_block
    assert "bottom: 0;" in sidebar_popover_block

    small_block = _media_block(css, "@media (max-width: 640px)")
    small_sidebar_block = _css_block(small_block, ".sidebar .floating-manual-wrapper {")
    assert "right: auto;" in small_sidebar_block
    assert "bottom: auto;" in small_sidebar_block

    popover_block = _css_block(css, ".manual-popover {")
    assert "position: absolute;" in popover_block
    assert "z-index: 120;" in popover_block

    base_template = _read("templates/base.html")
    macro_source = _read("templates/components/ui_macros.html")
    assert "ui.floating_manual_button()" in base_template
    assert "macro floating_manual_button" in macro_source
    assert "floating-manual-wrapper no-print" in macro_source
    assert _popover_is_inside_floating_wrapper(macro_source)


def test_v2_sidebar_turns_into_top_nav_on_narrow_screens() -> None:
    css = _read("web_new_test/static/css/style.css")
    ui_css = _read("static/css/ui_contract.css")

    app_block = _css_block(css, ".app-container {")
    assert "display: flex;" in app_block
    assert "min-width: 0;" in app_block

    main_block = _css_block(css, ".main-content {")
    assert "flex: 1;" in main_block
    assert "min-width: 0;" in main_block

    small_block = _media_block(css, "@media (max-width: 760px)")
    small_app_block = _css_block(small_block, ".app-container {")
    assert "display: block;" in small_app_block

    small_sidebar_block = _css_block(small_block, ".sidebar {")
    assert "width: 100%;" in small_sidebar_block
    assert "min-width: 0;" in small_sidebar_block

    small_sidebar_nav_block = _css_block(small_block, ".sidebar-nav {")
    assert "flex-direction: row;" in small_sidebar_nav_block
    assert "overflow-x: auto;" in small_sidebar_nav_block

    small_main_block = _css_block(small_block, ".main-content {")
    assert "width: 100%;" in small_main_block
    assert "min-width: 0;" in small_main_block

    small_header_block = _css_block(small_block, ".top-header {")
    assert "flex-wrap: wrap;" in small_header_block

    small_page_block = _css_block(small_block, ".page-content {")
    assert "padding: 1rem;" in small_page_block

    v2_base = _read("web_new_test/templates/base.html")
    sidebar_start = v2_base.index('class="sidebar"')
    manual_button = v2_base.index("ui.floating_manual_button()", sidebar_start)
    sidebar_end = v2_base.index('class="main-content"', sidebar_start)
    assert sidebar_start < manual_button < sidebar_end

    marker = "/* V2 窄屏时侧边栏会变成顶部导航，说明弹层需要改为向下展开 */"
    popover_mobile_css = ui_css[ui_css.index(marker) :]
    mobile_sidebar_popover = _css_block(popover_mobile_css, ".sidebar .manual-popover {")
    assert "left: 0;" in mobile_sidebar_popover
    assert "right: auto;" in mobile_sidebar_popover
    assert "top: calc(100% + 8px);" in mobile_sidebar_popover
    assert "bottom: auto;" in mobile_sidebar_popover
    assert "max-width: calc(100vw - 32px);" in mobile_sidebar_popover


def test_resource_dispatch_gantt_uses_css_class_not_inline_layout() -> None:
    source = _read("templates/scheduler/resource_dispatch.html")
    css = _read("static/css/ui_contract.css")

    assert 'id="rdGantt" style=' not in source
    assert 'id="rdGantt" class="aps-resource-gantt"' in source
    assert ".aps-resource-gantt" in css
    assert "min-height: 360px;" in _css_block(css, ".aps-resource-gantt {")


def main() -> None:
    test_excel_demo_current_people_table_has_scroll_and_readable_remark()
    test_excel_action_buttons_have_small_screen_fallback()
    test_action_and_run_status_wrap_on_small_screens()
    test_floating_manual_button_is_fixed_outside_sidebar()
    test_v2_sidebar_turns_into_top_nav_on_narrow_screens()
    test_resource_dispatch_gantt_uses_css_class_not_inline_layout()
    print("OK")


if __name__ == "__main__":
    main()
