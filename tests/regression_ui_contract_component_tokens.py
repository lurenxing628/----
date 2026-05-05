from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


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
    assert 'value="{{ submitted_value or hidden_value }}"' in toggle_block
