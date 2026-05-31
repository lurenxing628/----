from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    if rel_path == "templates/scheduler/analysis.html":
        for part in (
            "templates/scheduler/analysis_parts/_version_picker.html",
            "templates/scheduler/analysis_parts/_selected_overview.html",
        ):
            source += "\n" + (REPO_ROOT / part).read_text(encoding="utf-8")
    return source


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
        ".dispatch-query",
        ".dq-view",
        ".dq-object",
        ".dq-actions",
        ".aps-query-card .aps-resource-query-grid > .dq-plan",
        ".aps-summary-grid--version-overview",
        "@container (min-width: 900px)",
    ):
        assert token in css

    resource_source = _read("templates/scheduler/resource_dispatch.html")
    resource_form_start = resource_source.index(
        '<form method="get" action="{{ url_for(\'scheduler.resource_dispatch_page\') }}" class="aps-query-form-grid aps-resource-query-grid'
    )
    resource_form_end = resource_source.index("</form>", resource_form_start)
    resource_form = resource_source[resource_form_start:resource_form_end]

    actions_start = resource_form.index('class="aps-query-form-actions aps-resource-query-actions dq-actions"')
    assert actions_start > resource_form.index('name="version"')
    assert "{{ ui.button('查询', 'primary', 'md', type_attr='submit') }}" in resource_form
    assert "{{ ui.link_button('重置', url_for('scheduler.resource_dispatch_page'), 'secondary', 'md') }}" in resource_form
    assert "aps-filter-bar" not in resource_form
    assert "inline-flex-wrap" not in resource_form
    assert "form-row" not in resource_form
    assert "dispatch-query" in resource_form
    for token in ("dq-view", "dq-object", "dq-range", "dq-date", "dq-version", "dq-plan", "dq-actions"):
        assert token in resource_form
    assert "has-team-axis" in resource_form
    assert "has-custom-period" in resource_form


def test_scheduler_batch_manage_query_uses_batch_query_grid() -> None:
    for rel_path in (
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        source = _read(rel_path)
        assert "aps-query-form-grid aps-scheduler-batches-query-grid" in source
        assert "aps-query-form-actions" in source


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


def test_dark_theme_readonly_and_disabled_controls_stay_dark() -> None:
    css = _read("static/css/ui_contract.css")

    for token in (
        'html[data-theme="dark"] .readonly-value',
        'html[data-theme="dark"] .form-control:disabled',
        'html[data-theme="dark"] .form-control[readonly]',
        'html[data-theme="dark"] input:not([type="file"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):disabled',
        'html[data-theme="dark"] input:not([type="file"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="checkbox"]):not([type="radio"]):not([type="hidden"])[readonly]',
        'html[data-theme="dark"] input[type="number"]:not(.form-control)',
        'html[data-theme="dark"] input[type="file"]:disabled',
        'html[data-theme="dark"] input[type="file"]:disabled::file-selector-button',
        'html[data-theme="dark"] textarea:disabled',
        'html[data-theme="dark"] textarea[readonly]',
        'html[data-theme="dark"] select:disabled',
        'html[data-theme="dark"] .aps-button-like-disabled',
        'html[data-theme="dark"] .aps-summary-item-warning',
        'html[data-theme="dark"] .manual-toc a:hover',
        'html[data-theme="dark"] .badge-new',
        'html[data-theme="dark"] .badge-update',
        'html[data-theme="dark"] .badge-unchanged',
        'html[data-theme="dark"] .badge-skip',
        'html[data-theme="dark"] .badge-error',
        ".aps-summary-item-success",
        ".aps-summary-item-danger",
        ".aps-summary-item-info",
        ".aps-summary-item-neutral",
        'html[data-theme="dark"] .aps-summary-item-success',
        'html[data-theme="dark"] .aps-summary-item-danger',
        'html[data-theme="dark"] .aps-summary-item-info',
        'html[data-theme="dark"] .aps-summary-item-neutral',
    ):
        assert token in css

    readonly_base_start = css.index(".readonly-value")
    readonly_base_block = css[readonly_base_start : css.index("}", readonly_base_start)]
    assert "border: 1px solid var(--ui-border)" in readonly_base_block

    readonly_dark_start = css.index('html[data-theme="dark"] .readonly-value')
    readonly_dark_block = css[readonly_dark_start : css.index("}", readonly_dark_start)]
    assert "background: var(--ui-card-bg, #1e293b);" in readonly_dark_block
    assert "border-color: var(--ui-border, #334155);" in readonly_dark_block
    assert "color: var(--ui-text, #f1f5f9);" in readonly_dark_block
    assert "background: #fff" not in readonly_dark_block
    assert "background: #f8fafc" not in readonly_dark_block

    disabled_dark_start = css.index('html[data-theme="dark"] .form-control:disabled')
    disabled_dark_block = css[disabled_dark_start : css.index("}", disabled_dark_start)]
    assert "background: var(--ui-card-bg, #1e293b);" in disabled_dark_block
    assert "border: 1px solid var(--ui-border, #334155);" in disabled_dark_block
    assert "border-color: #334155;" in disabled_dark_block
    assert "color: #cbd5e1;" in disabled_dark_block
    assert "background: #fff" not in disabled_dark_block
    assert "background: #f8fafc" not in disabled_dark_block

    manual_toc_hover_start = css.index('html[data-theme="dark"] .manual-toc a:hover')
    manual_toc_hover_block = css[manual_toc_hover_start : css.index("}", manual_toc_hover_start)]
    assert "background: var(--ui-card-bg, #1e293b);" in manual_toc_hover_block
    assert "background: #e3f2fd" not in manual_toc_hover_block

    for token in (
        'html[data-theme="dark"] .badge-new',
        'html[data-theme="dark"] .badge-update',
        'html[data-theme="dark"] .badge-unchanged',
        'html[data-theme="dark"] .badge-skip',
        'html[data-theme="dark"] .badge-error',
    ):
        badge_dark_start = css.index(token)
        badge_dark_block = css[badge_dark_start : css.index("}", badge_dark_start)]
        assert "color:" in badge_dark_block
        assert "border-color:" in badge_dark_block
        assert "background: #fff" not in badge_dark_block
        assert "background: #f1f5f9" not in badge_dark_block
        assert "background: #fffbeb" not in badge_dark_block
        assert "background: #fef2f2" not in badge_dark_block

    summary_tones = {
        "warning": ("--ui-warning-bg", "--ui-warning-border"),
        "success": ("--ui-success-bg", "--ui-success-border"),
        "danger": ("--ui-danger-bg", "--ui-danger-border"),
        "info": ("--ui-info-bg", "--ui-info-border"),
        "neutral": ("--ui-neutral-bg", "--ui-neutral-border"),
    }
    for tone, (bg_token, border_token) in summary_tones.items():
        selector = f'html[data-theme="dark"] .aps-summary-item-{tone}'
        summary_dark_start = css.index(selector)
        summary_dark_block = css[summary_dark_start : css.index("}", summary_dark_start)]
        assert f"background: var({bg_token});" in summary_dark_block
        assert f"border-color: var({border_token});" in summary_dark_block

    assert "templates/system/backup.html" not in css


def main() -> None:
    test_first_batch_pages_do_not_use_old_flex_filter_rows()
    test_frontend_entry_cards_use_shared_stable_layout()
    test_scheduler_query_controls_use_page_specific_layouts()
    test_shared_form_span_helpers_are_scoped_to_form_grids()
    test_inline_editors_use_compact_grid_instead_of_card_form_grid()
    test_dark_theme_readonly_and_disabled_controls_stay_dark()
    print("OK")


if __name__ == "__main__":
    main()
