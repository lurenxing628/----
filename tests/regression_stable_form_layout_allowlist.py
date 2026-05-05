from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_first_batch_pages_do_not_use_old_flex_filter_rows() -> None:
    for rel_path in (
        "templates/personnel/calendar.html",
        "templates/system/logs.html",
        "templates/reports/overdue.html",
        "templates/reports/utilization.html",
        "templates/reports/downtime.html",
        "templates/equipment/downtime_batch.html",
        "templates/scheduler/batches.html",
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        source = _read(rel_path)
        assert "aps-filter-bar" not in source, rel_path
        assert "inline-flex-wrap" not in source, rel_path
        assert "form-row" not in source, rel_path


def test_frontend_entry_cards_use_shared_stable_layout() -> None:
    cases = (
        ("templates/process/list.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/process/detail.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/process/op_types_list.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/process/op_type_detail.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/process/suppliers_list.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/process/supplier_detail.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/equipment/list.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/equipment/detail.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/personnel/list.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/personnel/detail.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/personnel/teams.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/material/materials.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/material/batch_materials.html", ("aps-edit-form-grid", "aps-form-footer")),
        ("templates/scheduler/analysis.html", ("aps-query-card", "aps-query-form-grid", "aps-query-form-actions")),
        ("templates/scheduler/resource_dispatch.html", ("aps-query-card", "aps-query-form-grid", "aps-query-form-actions")),
        ("templates/scheduler/week_plan.html", ("aps-query-card", "aps-query-form-grid", "aps-query-form-actions")),
        ("templates/scheduler/batches.html", ("aps-query-form-grid", "aps-query-form-actions")),
        ("web_new_test/templates/scheduler/batches.html", ("aps-query-form-grid", "aps-query-form-actions")),
        ("templates/scheduler/batches_manage.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("web_new_test/templates/scheduler/batches_manage.html", ("aps-form-card", "aps-edit-form-grid", "aps-form-footer")),
        ("templates/scheduler/config.html", ("aps-settings-action-grid", "aps-query-form-grid", "aps-query-form-actions")),
        ("web_new_test/templates/scheduler/config.html", ("aps-settings-action-grid", "aps-query-form-grid", "aps-query-form-actions")),
        ("templates/components/excel_import.html", ("aps-query-form-grid", "aps-query-form-actions")),
        ("templates/scheduler/excel_import_batches.html", ("aps-query-form-grid", "aps-query-form-actions")),
    )
    for rel_path, required_tokens in cases:
        source = _read(rel_path)
        for token in required_tokens:
            assert token in source, f"{rel_path} 缺少 {token}"
        assert "form-row" not in source, rel_path
        assert "aps-filter-bar" not in source, rel_path


def test_scheduler_query_controls_use_page_specific_layouts() -> None:
    cases = (
        (
            "templates/scheduler/analysis.html",
            ("aps-version-picker-form", "aps-version-link-actions", "aps-summary-grid--version-overview"),
        ),
        ("templates/scheduler/week_plan.html", ("aps-week-plan-query-grid",)),
        ("templates/scheduler/resource_dispatch.html", ("aps-resource-query-grid", "aps-resource-query-actions")),
    )
    for rel_path, required_tokens in cases:
        source = _read(rel_path)
        for token in required_tokens:
            assert token in source, f"{rel_path} 缺少 {token}"

    css = _read("static/css/ui_contract.css")
    for token in (
        ".aps-version-picker-form",
        ".aps-week-plan-query-grid",
        ".aps-resource-query-grid",
        ".aps-summary-grid--version-overview",
        "@container (min-width: 900px)",
    ):
        assert token in css


def test_shared_form_span_helpers_are_scoped_to_form_grids() -> None:
    css = _read("static/css/ui_contract.css")
    assert ".aps-form-grid > .aps-form-span-2" in css
    assert ".aps-filter-bar > .aps-form-span-2" in css
    assert ".aps-form-grid > .aps-form-span-all" in css
    assert ".aps-filter-bar > .aps-form-span-all" in css
    assert ".aps-summary-grid > .aps-summary-span-all" in css


def test_inline_editors_use_compact_grid_instead_of_card_form_grid() -> None:
    source = _read("templates/process/detail.html")
    marker = "process.update_internal_hours"
    assert marker in source
    block = source[source.index(marker) : source.index("外协组", source.index(marker))]
    assert "aps-inline-edit-grid" in block
    assert "aps-form-grid" not in block


def main() -> None:
    test_first_batch_pages_do_not_use_old_flex_filter_rows()
    test_frontend_entry_cards_use_shared_stable_layout()
    test_scheduler_query_controls_use_page_specific_layouts()
    test_shared_form_span_helpers_are_scoped_to_form_grids()
    test_inline_editors_use_compact_grid_instead_of_card_form_grid()
    print("OK")


if __name__ == "__main__":
    main()
