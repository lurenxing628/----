from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _render_ui_macro(source: str) -> str:
    env = Environment(loader=FileSystemLoader(str(REPO_ROOT / "templates")))
    template = env.from_string("{% import 'components/ui_macros.html' as ui %}" + source)
    return template.render(
        toggle=SimpleNamespace(
            id="objectToggle",
            name="object_field",
            title="对象开关",
            desc="对象说明",
            checked_attr="checked",
            disabled_attr="disabled",
            value="yes",
            hidden_value="no",
            submitted_value="yes",
        ),
        details_notice=SimpleNamespace(
            title="说明",
            body="默认说明。",
            tone="warning",
            detail_label="查看明细",
            detail_items=(),
            footer="",
            role="",
            aria_live="",
        ),
        live_details_notice=SimpleNamespace(
            title="强说明",
            body="需要读到。",
            tone="danger",
            detail_label="查看明细",
            detail_items=("第一条",),
            footer="",
            role="alert",
            aria_live="assertive",
        ),
    )


def test_ui_contract_declares_semantic_tokens_and_components() -> None:
    css = _read("static/css/ui_contract.css")

    for token in (
        "--ui-surface",
        "--ui-surface-muted",
        "--ui-text-strong",
        "--ui-text-subtle",
        "--ui-focus-ring",
        "--ui-neutral-bg",
        "--ui-info-bg",
        "--ui-success-bg",
        "--ui-warning-bg",
        "--ui-danger-bg",
        "--ui-table-head-bg",
    ):
        assert token in css

    for selector in (
        ".aps-stack",
        ".aps-cluster",
        ".aps-split",
        ".aps-tone-neutral",
        ".aps-tone-info",
        ".aps-tone-success",
        ".aps-tone-warning",
        ".aps-tone-danger",
        ".aps-notice",
        ".aps-toggle-row",
        ".aps-table--fixed",
        ".aps-table--multiline",
        ".aps-table--editable",
        ".aps-table--actions-nowrap",
    ):
        assert selector in css


def test_ui_macros_expose_shared_contract_components() -> None:
    source = _read("templates/components/ui_macros.html")

    for macro_name in (
        "notice",
        "details_notice",
        "empty_state",
        "summary_grid",
        "toggle",
        "_toggle_row_internal",
    ):
        assert f"macro {macro_name}(" in source

    notice_start = source.index("{% macro notice(")
    notice_block = source[notice_start : source.index("{% endmacro %}", notice_start)]
    assert "role=''" in notice_block
    assert "aria_live=''" in notice_block
    assert "{% if role %} role=\"{{ role }}\"{% endif %}" in notice_block
    assert "{% if aria_live %} aria-live=\"{{ aria_live }}\"{% endif %}" in notice_block
    assert "role='status'" not in notice_block
    assert "aria_live='polite'" not in notice_block

    toggle_start = source.index("{% macro _toggle_row_internal(")
    toggle_block = source[toggle_start : source.index("{% endmacro %}", toggle_start)]
    checkbox_index = toggle_block.index('type="checkbox"')
    hidden_index = toggle_block.index('type="hidden"')
    assert checkbox_index < hidden_index
    assert 'value="{{ value }}"' in toggle_block
    assert "submitted_value" in toggle_block
    assert "final_submitted_value" not in toggle_block
    assert "disabled_attr == 'disabled' and checked_attr == 'checked'" not in toggle_block
    assert 'value="{{ submitted_value }}"' in toggle_block


def test_notice_macro_defaults_to_static_message_and_allows_explicit_live_role() -> None:
    default_rendered = _render_ui_macro("{{ ui.notice('普通提示', '这是静态页面提示。') }}")
    assert "aps-notice" in default_rendered
    assert 'role="' not in default_rendered
    assert "aria-live" not in default_rendered

    live_rendered = _render_ui_macro(
        "{{ ui.notice('强提醒', '需要立刻知道。', role='alert', aria_live='assertive') }}"
    )
    assert 'role="alert"' in live_rendered
    assert 'aria-live="assertive"' in live_rendered

    default_details = _render_ui_macro("{{ ui.details_notice(details_notice) }}")
    assert "aps-notice" in default_details
    assert 'role="' not in default_details
    assert "aria-live" not in default_details

    live_details = _render_ui_macro("{{ ui.details_notice(live_details_notice) }}")
    assert 'role="alert"' in live_details
    assert 'aria-live="assertive"' in live_details


def test_toggle_object_keeps_disabled_checked_hidden_value_safe() -> None:
    object_rendered = _render_ui_macro("{{ ui.toggle(toggle, class='object-row') }}")
    assert "object-row" in object_rendered
    assert 'id="objectToggle"' in object_rendered
    assert 'type="hidden" name="object_field" value="yes"' in object_rendered


def test_business_templates_do_not_call_low_level_toggle_row_macro_directly() -> None:
    allowed = {REPO_ROOT / "templates/components/ui_macros.html"}
    for template_root in (REPO_ROOT / "templates", REPO_ROOT / "web_new_test/templates"):
        for path in template_root.rglob("*.html"):
            if path in allowed:
                continue
            source = path.read_text(encoding="utf-8")
            assert "ui.toggle_row(" not in source, str(path.relative_to(REPO_ROOT))
            assert "ui._toggle_row_internal(" not in source, str(path.relative_to(REPO_ROOT))


def test_summary_item_legacy_macro_still_shows_dash_for_old_pages() -> None:
    rendered = _render_ui_macro("{{ ui.summary_item('旧摘要', none) }}{% call ui.summary_item_block('旧块', '') %}{% endcall %}")

    assert rendered.count('class="aps-summary-value">-</div>') == 2


def test_presenterized_pages_do_not_bypass_summary_item_values() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        assert "latest_head_items" in source
        assert "latest_meta_items" in source
        assert "latest_metric_items" in source
        assert "ui.summary_item('版本'" not in source
        assert "ui.summary_item('排产方式'" not in source
        assert "ui.summary_item('设备利用率'" not in source

    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)
        assert "current_config_summary_items" in source
        assert "current_auto_assign_persist_item" in source
        assert "ui.summary_item(current_config_state" not in source
        assert "ui.summary_item(auto_assign_persist_state" not in source

    backup_source = _read("templates/system/backup.html")
    plugin_block = backup_source[backup_source.index("扩展功能状态") :]
    assert "ui.summary_grid(page.plugin_summary_items" in plugin_block
    assert "ui.summary_item(" not in plugin_block


def test_business_toggle_routes_use_order_independent_form_parsers() -> None:
    route_contracts = {
        "web/routes/system_backup.py": (
            'form_yes_no_value(request.form, "auto_backup_enabled")',
            'form_yes_no_value(request.form, "auto_backup_cleanup_enabled")',
        ),
        "web/routes/system_logs.py": (
            'form_yes_no_value(request.form, "auto_log_cleanup_enabled")',
        ),
        "web/routes/domains/scheduler/scheduler_config.py": (
            "_SCHEDULER_CONFIG_TOGGLE_FIELDS",
            'form_yes_no_value(form, key)',
        ),
        "web/routes/system_plugins.py": (
            'form_yes_no_value(request.form, "enabled", default="no")',
        ),
        "web/routes/process_parts.py": (
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_run.py": (
            'form_optional_toggle_bool(request.form, "enforce_ready")',
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_batches.py": (
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_week_plan.py": (
            'form_optional_toggle_bool(request.form, "enforce_ready")',
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/process_excel_routes.py": (
            'form_toggle_bool(request.form, "strict_mode")',
            '"excelImportStrictMode"',
        ),
        "web/routes/domains/scheduler/scheduler_excel_batches.py": (
            'form_toggle_bool(request.form, "strict_mode")',
            'form_toggle_bool(request.form, "auto_generate_ops", default=False)',
            '"batchImportStrictMode"',
            '"batchImportAutoOps"',
        ),
    }
    for rel_path, markers in route_contracts.items():
        source = _read(rel_path)
        for marker in markers:
            assert marker in source, f"{rel_path} 缺少 {marker}"

    excel_utils_source = _read("web/routes/excel_utils.py")
    assert "strict_mode_enabled" not in excel_utils_source
