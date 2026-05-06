from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from web.viewmodels.ui_presenters import UiToggleRow

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _slice(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _render_excel_import_component() -> str:
    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        autoescape=select_autoescape(("html", "xml")),
    )
    env.filters["tojson_zh"] = lambda value, indent=None: "{}"
    template = env.from_string(
        "{% import 'components/ui_macros.html' as ui %}"
        "{% include 'components/excel_import.html' %}"
    )
    return template.render(
        title="测试导入",
        template_download_url="/template.xlsx",
        preview_url="/preview",
        confirm_url="/confirm",
        mode="overwrite",
        mode_options=(),
        strict_mode_supported=True,
        strict_mode_toggle=UiToggleRow(
            "excelImportStrictMode",
            "strict_mode",
            "发现问题就停下",
            "资料不完整时先停下，并告诉你哪一行、哪一项要补。",
            checked_attr="",
        ),
        strict_mode_help_text="勾选后：资料不完整就停下，并告诉你哪一行、哪一项要补。",
        preview_rows=(),
        existing_list=(),
        raw_rows_json="",
        preview_baseline="",
        filename="",
    )


def test_form_run_options_use_compact_toggle_fields_in_process_pages() -> None:
    list_source = _read("templates/process/list.html")
    create_block = _slice(list_source, 'action="{{ url_for(\'process.create_part\') }}"', "添加零件")
    assert "processCreateStrictMode" in create_block
    assert 'name="strict_mode" value="yes"' in create_block
    assert "aps-form-toggle-field" in create_block
    assert "aps-field-wide aps-form-toggle-field" in create_block
    assert "aps-settings-toggle-control-icon" in create_block
    assert "资料不完整就停下" in create_block
    assert "role=\"group\" aria-label=\"生成工序选项\"" not in create_block
    assert "aps-form-run-options" not in create_block
    assert "form-field aps-field-full" not in create_block

    detail_source = _read("templates/process/detail.html")
    reparse_block = _slice(detail_source, 'action="{{ url_for(\'process.reparse_part\'', "按路线重新生成工序清单")
    assert "processReparseStrictMode" in reparse_block
    assert 'name="strict_mode" value="yes"' in reparse_block
    assert "aps-form-toggle-field" in reparse_block
    assert "aps-field-wide aps-form-toggle-field" in reparse_block
    assert "role=\"group\" aria-label=\"生成工序选项\"" not in reparse_block
    assert "aps-form-run-options" not in reparse_block

    group_block = _slice(detail_source, 'action="{{ url_for(\'process.set_group_mode\'', "保存外协组设置")
    assert "processGroupStrictMode{{ gid }}" in group_block
    assert 'name="strict_mode" value="yes"' in group_block
    assert "aps-form-toggle-field" in group_block
    assert "aps-form-run-options" not in group_block


def test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels() -> None:
    for rel_path in ("templates/scheduler/batches_manage.html", "web_new_test/templates/scheduler/batches_manage.html"):
        source = _read(rel_path)
        block = _slice(source, 'action="{{ url_for(\'scheduler.create_batch\') }}"', "创建批次")
        assert "batchManageStrictMode" in block
        assert 'name="strict_mode" value="yes"' in block
        assert "aps-form-toggle-field" in block
        assert "aps-settings-toggle-control-icon" in block
        assert "<label>\n            <input type=\"checkbox\" name=\"strict_mode\"" not in block
        assert "form-field aps-field-full" not in block

    detail_source = _read("templates/scheduler/batch_detail.html")
    detail_block = _slice(detail_source, 'action="{{ url_for(\'scheduler.generate_ops\'', "查看刷新规则")
    assert "aps-inline-run-action" in detail_block
    assert "batchDetailStrictMode" in detail_block
    assert 'name="strict_mode" value="yes"' in detail_block
    assert "d-inline-block mr-3" not in detail_block

    import_source = _read("templates/scheduler/excel_import_batches.html")
    upload_block = _slice(import_source, 'action="{{ preview_url }}"', "上传 Excel 并检查")
    assert "aps-import-option-list" in upload_block
    assert "batchImportAutoOps" in upload_block
    assert 'name="auto_generate_ops" value="1"' in upload_block
    assert "ui.toggle(strict_mode_toggle" in upload_block
    assert "<label><input type=\"checkbox\"" not in upload_block

    component_source = _read("templates/components/excel_import.html")
    macro_source = _read("templates/components/ui_macros.html")
    assert "aps-import-option-list" in component_source
    assert "ui.toggle(strict_mode_toggle" in component_source
    assert "strict_mode_label or" not in component_source
    assert "strict_mode_help or" not in component_source
    assert "checked_attr='checked' if strict_mode else ''" not in component_source
    assert "value=\"{{ value }}\"" in macro_source
    assert "final_submitted_value" in macro_source
    assert "disabled_attr == 'disabled' and checked_attr == 'checked'" in macro_source
    assert "<label>\n          <input type=\"checkbox\" name=\"strict_mode\"" not in component_source

    route_source = _read("web/routes/domains/scheduler/scheduler_excel_batches.py")
    assert "UiToggleRow(" in route_source
    assert "\"batchImportStrictMode\"" in route_source


def test_excel_import_component_renders_strict_mode_toggle_fields() -> None:
    html = _render_excel_import_component()

    assert 'id="excelImportStrictMode"' in html
    assert 'type="checkbox"' in html
    assert 'name="strict_mode"' in html
    assert 'value="yes"' in html
    assert 'type="hidden" name="strict_mode" value="no"' in html
    assert html.index('id="excelImportStrictMode"') < html.index('type="hidden" name="strict_mode" value="no"')


def test_run_option_css_is_scoped_to_the_right_surfaces() -> None:
    css = _read("static/css/ui_contract.css")
    assert ".aps-form-toggle-field" in css
    assert ".aps-inline-run-action" in css
    assert ".aps-import-option-list" in css
    assert ".aps-run-panel-grid > .aps-run-options" in css
    assert ".aps-run-options-title" in css
    assert ".aps-run-option-row + .aps-run-option-row" in css
    assert ".aps-run-option-note + .aps-run-option-row" in css
    assert ".aps-form-toggle-field .aps-run-option-row" in css
    assert ".aps-run-option-row .aps-toggle-control" in css
    assert ".aps-run-option-row .aps-toggle-title" in css


def main() -> None:
    test_form_run_options_use_compact_toggle_fields_in_process_pages()
    test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels()
    test_excel_import_component_renders_strict_mode_toggle_fields()
    test_run_option_css_is_scoped_to_the_right_surfaces()
    print("OK")


if __name__ == "__main__":
    main()
