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


def main() -> None:
    test_gantt_control_area_does_not_nest_generic_form_grids()
    test_gantt_control_css_keeps_query_controls_horizontal()
    print("OK")


if __name__ == "__main__":
    main()
