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
        )
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
        "toggle_row",
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

    toggle_start = source.index("{% macro toggle_row(")
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


def test_toggle_object_keeps_disabled_checked_hidden_value_safe() -> None:
    direct = _render_ui_macro(
        "{{ ui.toggle_row('directToggle', 'direct_field', '直接开关', '直接说明', checked_attr='checked', disabled_attr='disabled', submitted_value='yes') }}"
    )
    assert 'id="directToggle"' in direct
    assert 'type="checkbox"' in direct
    assert 'name="direct_field" value="yes"' in direct
    assert 'type="hidden" name="direct_field" value="yes"' in direct

    direct_hidden = _render_ui_macro(
        "{{ ui.toggle_row('directHiddenToggle', 'direct_hidden_field', '直接开关', '直接说明', submitted_value='0') }}"
    )
    assert 'id="directHiddenToggle"' in direct_hidden
    assert 'type="hidden" name="direct_hidden_field" value="0"' in direct_hidden

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
