from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARD_MIN_WIDTH_CLASSES = ("min-w-320", "min-w-360", "min-w-420")


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _css_block(source: str, selector: str) -> str:
    start = source.index(selector)
    return source[start : source.index("}", start) + 1]


def _template_grid_direct_children(source: str, grid_class: str) -> list[str]:
    children: list[str] = []
    for match in re.finditer(rf'<div class="[^"]*\b{re.escape(grid_class)}\b[^"]*">', source):
        grid_start = match.end()
        grid_end = source.find("</div>", grid_start)
        if grid_end < 0:
            continue
        grid_block = source[grid_start:grid_end]
        children.extend(re.findall(r'<div class="([^"]*)"', grid_block))
    return children


def test_excel_import_upload_field_uses_semantic_responsive_class() -> None:
    source = _read("templates/components/excel_import.html")
    css = _read("static/css/ui_contract.css")

    upload_start = source.index('id="excelImportFile"')
    upload_block = source[source.rfind("<div", 0, upload_start) : source.index("</div>", upload_start)]
    assert "aps-excel-upload-field" in upload_block
    assert "min-w-320" not in upload_block
    assert "aps-excel-upload-input" in upload_block

    field_block = _css_block(css, ".aps-excel-upload-field,")
    assert "min-width: min(100%, 320px);" in field_block

    input_block = _css_block(css, '.aps-excel-upload-field input[type="file"],')
    for token in ("width: 100%;", "min-width: 0;", "max-width: 100%;", "box-sizing: border-box;"):
        assert token in input_block


def test_batch_material_select_fields_do_not_use_hard_min_width_classes() -> None:
    source = _read("templates/material/batch_materials.html")
    css = _read("static/css/ui_contract.css")

    for field_id, semantic_class in (
        ("batchMaterialBatchSelect", "aps-batch-material-batch-field"),
        ("batchMaterialMaterialSelect", "aps-batch-material-material-field"),
    ):
        field_start = source.index(f'id="{field_id}"')
        field_block = source[source.rfind("<div", 0, field_start) : source.index("</div>", field_start)]
        assert semantic_class in field_block
        for hard_class in HARD_MIN_WIDTH_CLASSES:
            assert hard_class not in field_block

    semantic_block = _css_block(css, ".aps-excel-upload-field,")
    assert ".aps-batch-material-batch-field" in semantic_block
    assert ".aps-batch-material-material-field" in semantic_block
    assert "min-width: min(100%, 320px);" in semantic_block

    small_block = css[css.index("@media (max-width: 520px)") :]
    assert ".aps-batch-material-batch-field" in small_block
    assert ".aps-batch-material-material-field" in small_block
    assert "min-width: 0;" in small_block


def test_targeted_form_grids_do_not_put_hard_min_width_on_direct_children() -> None:
    for rel_path in ("templates/components/excel_import.html", "templates/material/batch_materials.html"):
        source = _read(rel_path)
        direct_children = (
            _template_grid_direct_children(source, "aps-query-form-grid")
            + _template_grid_direct_children(source, "aps-edit-form-grid")
        )
        offenders = [
            class_value
            for class_value in direct_children
            if any(hard_class in class_value.split() for hard_class in HARD_MIN_WIDTH_CLASSES)
        ]
        assert offenders == [], f"{rel_path} 仍有硬 min-width 直接压在响应式 grid 子项上：{offenders}"


def main() -> None:
    test_excel_import_upload_field_uses_semantic_responsive_class()
    test_batch_material_select_fields_do_not_use_hard_min_width_classes()
    test_targeted_form_grids_do_not_put_hard_min_width_on_direct_children()
    print("OK")


if __name__ == "__main__":
    main()
