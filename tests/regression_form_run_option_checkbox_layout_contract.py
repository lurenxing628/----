from __future__ import annotations

import importlib
import io
import re
import sys
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


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)

    from core.infrastructure.database import ensure_schema

    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _with_db(db_path: str):
    from core.infrastructure.database import get_connection

    return get_connection(db_path)


def _seed_strict_mode_render_data(db_path: str) -> None:
    conn = _with_db(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_RENDER", "渲染测试零件", "10表处理20总检", "no"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO ExternalGroups
                (group_id, part_no, start_seq, end_seq, merge_mode, total_days)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("G_RENDER", "P_RENDER", 10, 20, "separate", 2),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO Batches
                (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RENDER", "P_RENDER", "渲染测试零件", 1, "2026-05-01", "normal", "yes", "pending"),
        )
        conn.commit()
    finally:
        conn.close()


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def _html(response) -> str:
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _assert_toggle_field_order(
    html: str,
    *,
    checkbox_id: str,
    field_name: str = "strict_mode",
    checkbox_value: str = "yes",
    hidden_value: str = "no",
) -> None:
    checkbox_index = html.index(f'id="{checkbox_id}"')
    checkbox_end = html.index(">", checkbox_index)
    checkbox_tag = html[checkbox_index:checkbox_end]
    assert 'type="checkbox"' in checkbox_tag
    assert f'name="{field_name}"' in checkbox_tag
    assert f'value="{checkbox_value}"' in checkbox_tag

    hidden_pattern = f'type="hidden" name="{field_name}" value="{hidden_value}"'
    hidden_index = html.index(hidden_pattern, checkbox_index)
    assert checkbox_index < hidden_index


def _assert_disabled_display_checkbox_without_name(html: str, *, value: str) -> None:
    tags = [
        tag
        for tag in re.findall(r"<input[^>]+disabled[^>]*>", html)
        if f'value="{value}"' in tag and 'type="checkbox"' in tag
    ]
    assert tags
    assert all("name=" not in tag for tag in tags)


def test_form_run_options_use_compact_toggle_fields_in_process_pages() -> None:
    list_source = _read("templates/process/list.html")
    process_route_source = _read("web/routes/process_parts.py")
    create_block = _slice(list_source, 'action="{{ url_for(\'process.create_part\') }}"', "添加零件")
    assert '"processCreateStrictMode"' in process_route_source
    assert "ui.toggle(create_strict_toggle" in create_block
    assert "aps-form-toggle-field" in create_block
    assert "aps-field-wide aps-form-toggle-field" in create_block
    assert "aps-settings-toggle-control-icon" not in create_block
    assert "资料不完整就停下" in _read("web/viewmodels/strict_mode_toggles.py")
    assert "role=\"group\" aria-label=\"生成工序选项\"" not in create_block
    assert "aps-form-run-options" not in create_block
    assert "form-field aps-field-full" not in create_block

    detail_source = _read("templates/process/detail.html")
    reparse_block = _slice(detail_source, 'action="{{ url_for(\'process.reparse_part\'', "按路线重新生成工序清单")
    assert '"processReparseStrictMode"' in process_route_source
    assert "ui.toggle(reparse_strict_toggle" in reparse_block
    assert "aps-form-toggle-field" in reparse_block
    assert "aps-field-wide aps-form-toggle-field" in reparse_block
    assert "role=\"group\" aria-label=\"生成工序选项\"" not in reparse_block
    assert "aps-form-run-options" not in reparse_block

    group_block = _slice(detail_source, 'action="{{ url_for(\'process.set_group_mode\'', "保存外协组设置")
    assert "ui.toggle(g.strict_mode_toggle" in group_block
    assert "aps-form-toggle-field" in group_block
    assert "aps-form-run-options" not in group_block


def test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels() -> None:
    for rel_path in ("templates/scheduler/batches_manage.html", "web_new_test/templates/scheduler/batches_manage.html"):
        source = _read(rel_path)
        scheduler_batches_route_source = _read("web/routes/domains/scheduler/scheduler_batches.py")
        block = _slice(source, 'action="{{ url_for(\'scheduler.create_batch\') }}"', "创建批次")
        assert '"batchManageStrictMode"' in scheduler_batches_route_source
        assert "ui.toggle(batch_manage_strict_toggle" in block
        assert "aps-form-toggle-field" in block
        assert "aps-settings-toggle-control-icon" not in block
        assert "<label>\n            <input type=\"checkbox\" name=\"strict_mode\"" not in block
        assert "form-field aps-field-full" not in block

    detail_source = _read("templates/scheduler/batch_detail.html")
    detail_route_source = _read("web/routes/domains/scheduler/scheduler_batch_detail.py")
    detail_block = _slice(detail_source, 'action="{{ url_for(\'scheduler.generate_ops\'', "查看刷新规则")
    assert "aps-inline-run-action" in detail_block
    assert '"batchDetailStrictMode"' in detail_route_source
    assert "ui.toggle(batch_detail_strict_toggle" in detail_block
    assert "d-inline-block mr-3" not in detail_block

    import_source = _read("templates/scheduler/excel_import_batches.html")
    upload_block = _slice(import_source, 'action="{{ preview_url }}"', "上传 Excel 并检查")
    assert "aps-import-option-list" in upload_block
    assert "ui.toggle(auto_generate_ops_toggle" in upload_block
    assert "ui.toggle(strict_mode_toggle" in upload_block
    assert "aps-settings-toggle-control-icon" not in upload_block
    assert "<label><input type=\"checkbox\"" not in upload_block

    component_source = _read("templates/components/excel_import.html")
    macro_source = _read("templates/components/ui_macros.html")
    assert "aps-import-option-list" in component_source
    assert "ui.toggle(strict_mode_toggle" in component_source
    assert "strict_mode_label or" not in component_source
    assert "strict_mode_help or" not in component_source
    assert "checked_attr='checked' if strict_mode else ''" not in component_source
    assert "value=\"{{ value }}\"" in macro_source
    assert "value=\"{{ submitted_value }}\"" in macro_source
    assert "final_submitted_value" not in macro_source
    assert "disabled_attr == 'disabled' and checked_attr == 'checked'" not in macro_source
    assert "<label>\n          <input type=\"checkbox\" name=\"strict_mode\"" not in component_source

    route_source = _read("web/routes/domains/scheduler/scheduler_excel_batches.py")
    assert "UiToggleRow(" in route_source
    assert "\"batchImportStrictMode\"" in route_source
    assert "\"batchImportAutoOps\"" in route_source
    assert 'form_toggle_bool(request.form, "auto_generate_ops", default=False)' in route_source

    process_route_source = _read("web/routes/process_excel_routes.py")
    process_template_source = _read("templates/process/excel_import_routes.html")
    assert '{% include "components/excel_import.html" with context %}' in process_template_source
    assert "strict_mode_supported=True" in process_route_source
    assert "UiToggleRow(" in process_route_source
    assert "\"excelImportStrictMode\"" in process_route_source
    assert "strict_mode_help_text" in process_route_source
    assert process_route_source.count('form_toggle_bool(request.form, "strict_mode")') == 2

    process_parts_source = _read("web/routes/process_parts.py")
    assert process_parts_source.count('form_toggle_bool(request.form, "strict_mode")') == 3
    assert "_strict_mode_enabled" not in process_parts_source
    assert 'request.form.get("strict_mode")' not in process_parts_source

    scheduler_batches_source = _read("web/routes/domains/scheduler/scheduler_batches.py")
    assert scheduler_batches_source.count('form_toggle_bool(request.form, "strict_mode")') == 2
    assert "_strict_mode_enabled" not in scheduler_batches_source
    assert 'request.form.get("strict_mode")' not in scheduler_batches_source

    excel_utils_source = _read("web/routes/excel_utils.py")
    assert "strict_mode_enabled" not in excel_utils_source


def test_excel_import_component_renders_strict_mode_toggle_fields() -> None:
    html = _render_excel_import_component()

    assert 'id="excelImportStrictMode"' in html
    assert 'type="checkbox"' in html
    assert 'name="strict_mode"' in html
    assert 'value="yes"' in html
    assert 'type="hidden" name="strict_mode" value="no"' in html
    assert html.index('id="excelImportStrictMode"') < html.index('type="hidden" name="strict_mode" value="no"')


def test_process_pages_render_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    client = app.test_client()

    list_html = _html(client.get("/process/"))
    _assert_toggle_field_order(list_html, checkbox_id="processCreateStrictMode")

    detail_html = _html(client.get("/process/parts/P_RENDER"))
    _assert_toggle_field_order(detail_html, checkbox_id="processReparseStrictMode")
    _assert_toggle_field_order(detail_html, checkbox_id="processGroupStrictModeG_RENDER")


def test_scheduler_batch_pages_render_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    client = app.test_client()

    manage_html = _html(client.get("/scheduler/batches"))
    _assert_toggle_field_order(manage_html, checkbox_id="batchManageStrictMode")

    detail_html = _html(client.get("/scheduler/batches/B_RENDER"))
    _assert_toggle_field_order(detail_html, checkbox_id="batchDetailStrictMode")


def test_process_excel_page_renders_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    html = _html(client.get("/process/excel/routes"))
    _assert_toggle_field_order(html, checkbox_id="excelImportStrictMode")


def test_batch_excel_confirm_page_uses_hidden_strict_mode_and_readonly_display(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    client = app.test_client()

    preview_response = client.post(
        "/scheduler/excel/batches/preview",
        data={
            "mode": "overwrite",
            "auto_generate_ops": "1",
            "strict_mode": "yes",
            "file": (
                _make_xlsx_bytes(
                    ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                    [
                        {
                            "批次号": "B_RENDER_EXCEL",
                            "图号": "P_RENDER",
                            "数量": 2,
                            "交期": "2026-05-10",
                            "优先级": "normal",
                            "齐套": "yes",
                            "齐套日期": None,
                            "备注": "strict-mode-render",
                        }
                    ],
                ),
                "batches.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    html = _html(preview_response)

    assert 'type="hidden" name="strict_mode" value="yes"' in html
    _assert_disabled_display_checkbox_without_name(html, value="yes")


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
