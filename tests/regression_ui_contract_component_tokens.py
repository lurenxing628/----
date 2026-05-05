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
        "empty_state",
        "summary_grid",
        "toggle",
        "toggle_row",
    ):
        assert f"macro {macro_name}(" in source

    notice_start = source.index("{% macro notice(")
    notice_block = source[notice_start : source.index("{% endmacro %}", notice_start)]
    assert "role='status'" in notice_block
    assert "aria_live='polite'" in notice_block
    assert 'role="{{ role }}"' in notice_block

    toggle_start = source.index("{% macro toggle_row(")
    toggle_block = source[toggle_start : source.index("{% endmacro %}", toggle_start)]
    checkbox_index = toggle_block.index('type="checkbox"')
    hidden_index = toggle_block.index('type="hidden"')
    assert checkbox_index < hidden_index
    assert 'value="{{ value }}"' in toggle_block
    assert "submitted_value" in toggle_block
    assert "final_submitted_value" in toggle_block
    assert "disabled_attr == 'disabled' and checked_attr == 'checked'" in toggle_block
    assert 'value="{{ final_submitted_value }}"' in toggle_block


def test_toggle_macros_keep_disabled_checked_hidden_value_safe() -> None:
    direct = _render_ui_macro(
        "{{ ui.toggle_row('directToggle', 'direct_field', '直接开关', '直接说明', checked_attr='checked', disabled_attr='disabled') }}"
    )
    assert 'id="directToggle"' in direct
    assert 'type="checkbox"' in direct
    assert 'name="direct_field" value="yes"' in direct
    assert 'type="hidden" name="direct_field" value="yes"' in direct

    object_rendered = _render_ui_macro("{{ ui.toggle(toggle, class='object-row') }}")
    assert "object-row" in object_rendered
    assert 'id="objectToggle"' in object_rendered
    assert 'type="hidden" name="object_field" value="yes"' in object_rendered
