from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_calendar_forms_use_stable_date_picker_layout() -> None:
    css = _read("static/css/ui_contract.css")
    assert ".aps-calendar-form-grid" in css
    assert ".aps-date-picker-field" in css
    assert "repeat(auto-fit, minmax(min(100%, 220px), 1fr))" in css
    assert "container-type: inline-size" in css
    assert "align-items: start;" in css
    assert ".wc-date-wrap #wcDateHint:empty" in css
    assert "aps-calendar-actions {\n  display: flex;" in css
    assert "@container (min-width: 720px)" in css
    assert "@container (max-width: 719px)" in css
    assert ".aps-calendar-date-field {\n    grid-column: 1 / span 2;" in css
    assert ".aps-calendar-day-type {\n    grid-column: 3;\n    grid-row: 1;" in css
    assert ".aps-calendar-start {\n    grid-column: 4;\n    grid-row: 1;" in css
    assert ".aps-table-scroll > .aps-calendar-table" in css
    assert "min-width: 1240px;" in css
    max_900_block = css.split("@media (max-width: 900px)", 1)[1].split("@media", 1)[0]
    assert ".aps-calendar-date-field" not in max_900_block

    for rel_path in ("templates/scheduler/calendar.html", "templates/personnel/calendar.html"):
        source = _read(rel_path)
        assert "wc-card-allow-overflow" in source
        assert "aps-calendar-form-grid" in source
        assert "aps-date-picker-field" in source
        assert "aps-calendar-actions" in source
        assert "aps-table-scroll" in source
        assert "aps-calendar-table" in source
        assert "aps-calendar-remark-cell" in source
        assert source.index('class="aps-calendar-actions"') > source.index('class="aps-calendar-form-grid"')
        assert source.index('class="aps-calendar-actions"') > source.index('name="remark"')
        for field_name in (
            "date",
            "day_type",
            "shift_start",
            "shift_end",
            "shift_hours",
            "efficiency",
            "allow_normal",
            "allow_urgent",
            "remark",
        ):
            assert f'name="{field_name}"' in source
        for element_id in ("wcDateInput", "wcDatePickBtn", "wcDateHint", "wcCalendarPanel"):
            assert element_id in source
        for coord_class in (
            "aps-calendar-date-field",
            "aps-calendar-day-type",
            "aps-calendar-start",
            "aps-calendar-end",
            "aps-calendar-hours",
            "aps-calendar-efficiency",
            "aps-calendar-allow-normal",
            "aps-calendar-allow-urgent",
            "aps-calendar-remark",
        ):
            assert coord_class in source
        assert "calendar-upsert-row" not in source
        assert "inline-flex-wrap" not in source[source.index("新增 / 更新某一天") :]
        if rel_path == "templates/personnel/calendar.html":
            form_block = source[source.index("新增 / 更新某一天") : source.index("已配置", source.index("新增 / 更新某一天"))]
            assert 'class="w-120"' not in form_block
            assert 'class="w-140"' not in form_block
            assert 'class="w-160"' not in form_block


def main() -> None:
    test_calendar_forms_use_stable_date_picker_layout()
    print("OK")


if __name__ == "__main__":
    main()
