from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_gantt_control_area_does_not_nest_generic_form_grids() -> None:
    for rel_path in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        source = _read(rel_path)
        assert "aps-gantt-control-panel" in source, rel_path
        assert "aps-gantt-control-row" in source, rel_path
        assert "aps-gantt-range-form" in source, rel_path
        assert "aps-gantt-version-summary" in source, rel_path
        assert 'class="aps-form-grid"' not in source, rel_path
        assert 'class="form-field aps-gantt-control-group"' not in source, rel_path
        assert 'class="aps-gantt-control-group"' in source, rel_path
        assert source.index("aps-gantt-range-form") < source.index("aps-gantt-version-summary")


def test_gantt_control_css_keeps_query_controls_horizontal() -> None:
    css = _read("static/css/aps_gantt.css")
    for token in (
        ".aps-gantt-control-panel",
        ".aps-gantt-control-row",
        ".aps-gantt-range-form",
        ".aps-gantt-version-summary",
        "grid-template-columns: repeat(4, minmax(150px, 1fr)) auto;",
        "grid-column: 1 / -1;",
        "width: fit-content;",
        ".aps-gantt-control-group > label",
    ):
        assert token in css


def test_gantt_range_form_keeps_tablet_and_phone_breakpoints() -> None:
    css = _read("static/css/aps_gantt.css")
    tablet_block = css.split("@media (max-width: 980px)", 1)[1].split("@media", 1)[0]
    phone_block = css.split("@media (max-width: 560px)", 1)[1].split("@media", 1)[0]

    assert ".aps-gantt-range-form" in tablet_block
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in tablet_block
    assert ".aps-gantt-range-form .aps-query-form-actions" in tablet_block
    assert "grid-column: 1 / -1;" in tablet_block

    assert ".aps-gantt-range-form" in phone_block
    assert "grid-template-columns: 1fr;" in phone_block
    assert ".aps-gantt-range-form .aps-query-form-actions .btn" in phone_block
    assert "width: 100%;" in phone_block


def test_gantt_filter_checks_does_not_force_overwide_column_near_900px() -> None:
    css = _read("static/css/aps_gantt.css")
    base_block = css[css.index(".aps-gantt-filter-checks {") : css.index("}", css.index(".aps-gantt-filter-checks {"))]
    desktop_block = css.split("@media (min-width: 900px)", 1)[1]

    assert "min-width: 0;" in base_block
    assert ".aps-gantt-filter-checks" in desktop_block
    assert "min-width: min(100%, 260px);" in desktop_block
    assert "min-width: 320px;" not in desktop_block


def test_gantt_popup_keeps_readable_width_and_autofits_visible_area() -> None:
    css = _read("static/css/aps_gantt.css")
    fit_js = _read("static/js/gantt_popup_fit.js")

    for token in (
        "#gantt .gantt-container .popup-wrapper",
        "#rdGantt .gantt-container .popup-wrapper",
        "width: min(420px, calc(100vw - 32px));",
        "min-width: min(160px, calc(100vw - 32px));",
        "box-sizing: border-box;",
    ):
        assert token in css

    for token in (
        "window.__APS_GANTT_POPUP_FIT__",
        "function computeFitGeometry(input, options)",
        "availableWidth",
        "popup.style.maxWidth",
        "window.ResizeObserver",
        "container.scrollLeft",
        "container.clientWidth",
        "requestAnimationFrame",
    ):
        assert token in fit_js

    for rel_path in ("templates/scheduler/gantt.html", "templates/scheduler/resource_dispatch.html"):
        assert "js/gantt_popup_fit.js" in _read(rel_path)


def main() -> None:
    test_gantt_control_area_does_not_nest_generic_form_grids()
    test_gantt_control_css_keeps_query_controls_horizontal()
    test_gantt_range_form_keeps_tablet_and_phone_breakpoints()
    test_gantt_filter_checks_does_not_force_overwide_column_near_900px()
    test_gantt_popup_keeps_readable_width_and_autofits_visible_area()
    print("OK")


if __name__ == "__main__":
    main()
