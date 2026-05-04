from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_equipment_downtime_batch_layout_keeps_scope_contract() -> None:
    source = _read("templates/equipment/downtime_batch.html")

    assert "ui.aps_page_hero" in source
    assert "本页用于" not in source  # 由 aps_page_hero 宏统一渲染，模板不要再手写旧段落。
    assert "aps-downtime-form-card" in source
    assert "aps-downtime-form-grid" in source
    assert "aps-filter-grid" not in source
    assert "form-row" not in source
    for marker in (
        "aps-downtime-scope-type",
        "aps-downtime-scope-value",
        "aps-downtime-start",
        "aps-downtime-end",
        "aps-downtime-reason",
        "aps-downtime-detail",
        "aps-downtime-actions",
    ):
        assert marker in source

    assert 'name="scope_type"' in source
    assert source.count('name="scope_value"') == 2
    for element_id in ("scopeType", "scopeValueMachine", "scopeValueCategory"):
        assert element_id in source

    form_start = source.index('<form method="post" action="{{ url_for(\'equipment.downtime_batch_create\') }}">')
    form_end = source.index("</form>", form_start)
    form_block = source[form_start:form_end]
    for field_name in ("start_time", "end_time", "reason_code", "reason_detail"):
        assert f'name="{field_name}"' in form_block
    assert "downtime_batch.js" in source

    css = _read("static/css/ui_contract.css")
    assert "@container (min-width: 1100px)" in css


def main() -> None:
    test_equipment_downtime_batch_layout_keeps_scope_contract()
    print("OK")


if __name__ == "__main__":
    main()
