from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.services.common.excel_templates import get_template_definition
from core.services.process import UnitExcelConverter


def _definition_enum_values_by_header(definition: Mapping[str, Any]) -> Dict[str, List[str]]:
    headers = [str(item) for item in (definition.get("headers") or [])]
    enum_cols = ((definition.get("format_spec") or {}).get("enum_cols") or {})
    out: Dict[str, List[str]] = {}
    for raw_col_idx, values in enum_cols.items():
        col_idx = int(raw_col_idx)
        out[headers[col_idx]] = [str(item).strip() for item in (values or []) if str(item).strip()]
    return out


def _inline_validation_values(formula1: Any) -> List[str]:
    raw = str(formula1 or "").strip()
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _data_validation_contracts(ws: Any, one_based_col_idx: int) -> List[Dict[str, Any]]:
    contracts: List[Dict[str, Any]] = []
    for data_validation in ws.data_validations.dataValidation:
        if data_validation.type != "list":
            continue
        for cell_range in data_validation.sqref.ranges:
            if cell_range.min_col <= one_based_col_idx <= cell_range.max_col and cell_range.min_row <= 2 <= cell_range.max_row:
                contracts.append(
                    {
                        "values": _inline_validation_values(data_validation.formula1),
                        "range": str(cell_range),
                    }
                )
                break
    return contracts


def _nonempty_rows(ws: Any, width: int) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for row_idx in range(2, ws.max_row + 1):
        values = [ws.cell(row_idx, col_idx).value for col_idx in range(1, width + 1)]
        if any(value not in (None, "") for value in values):
            rows.append(values)
    return rows


def _expected_column_width(ws: Any, one_based_col_idx: int, explicit_width: int) -> int:
    content_width = 0
    for row in ws.iter_rows(min_col=one_based_col_idx, max_col=one_based_col_idx):
        value = row[0].value
        content_width = max(content_width, len("" if value is None else str(value)))
    return max(min(max(content_width + 2, 12), 36), int(explicit_width))


def _assert_layout_matches_definition(ws: Any, definition: Mapping[str, Any], filename: str) -> None:
    expected_headers = [str(item) for item in definition.get("headers") or []]
    format_spec = definition.get("format_spec") or {}
    rows = _nonempty_rows(ws, len(expected_headers))
    format_max_row = max(len(rows) + 200, 500)

    assert ws.freeze_panes == "A2", f"{filename} 应冻结首行"
    for cell in ws[1][: len(expected_headers)]:
        assert cell.font.bold is True, f"{filename} 表头应加粗"
        assert cell.alignment.horizontal == "center", f"{filename} 表头应水平居中"
        assert cell.alignment.vertical == "center", f"{filename} 表头应垂直居中"

    for zero_based_col_idx in format_spec.get("text_cols", []) or []:
        col_letter = get_column_letter(int(zero_based_col_idx) + 1)
        for row_idx in (2, max(2, len(rows) + 1), format_max_row):
            assert ws[f"{col_letter}{row_idx}"].number_format == "@", f"{filename} 的 {col_letter} 列应按文本格式交付"

    for zero_based_col_idx, width in (format_spec.get("column_widths") or {}).items():
        col_letter = get_column_letter(int(zero_based_col_idx) + 1)
        expected_width = _expected_column_width(ws, int(zero_based_col_idx) + 1, int(width))
        actual_width = ws.column_dimensions[col_letter].width
        assert abs(float(actual_width or 0) - float(expected_width)) < 0.01, (
            f"{filename} 的 {col_letter} 列宽应为 {expected_width}，实际为 {actual_width}"
        )

    for header, values in _definition_enum_values_by_header(definition).items():
        one_based_col_idx = expected_headers.index(header) + 1
        expected_range = f"{get_column_letter(one_based_col_idx)}2:{get_column_letter(one_based_col_idx)}{format_max_row}"
        assert _data_validation_contracts(ws, one_based_col_idx) == [{"values": values, "range": expected_range}]


def _read_workbook_rows(path: Path, headers: Sequence[str]) -> List[List[Any]]:
    workbook = load_workbook(path, data_only=True)
    try:
        return _nonempty_rows(workbook.active, len(headers))
    finally:
        workbook.close()


def test_op_type_conversion_output_matches_current_converter_result_and_layout() -> None:
    filename = "工种配置.xlsx"
    definition = get_template_definition(filename)
    headers = [str(item) for item in definition.get("headers") or []]
    path = REPO_ROOT / "templates_excel" / "转换输出" / filename
    source_path = REPO_ROOT / "templates_excel" / "回转壳体单元产品数据.xlsx"
    expected_rows = [
        [row.get(header) for header in headers]
        for row in UnitExcelConverter().convert(str(source_path)).op_types_rows
    ]

    workbook = load_workbook(path, data_only=True)
    try:
        ws = workbook.active
        assert [ws.cell(1, col_idx).value for col_idx in range(1, len(headers) + 1)] == headers
        _assert_layout_matches_definition(ws, definition, filename)
        assert _nonempty_rows(ws, len(headers)) == expected_rows
    finally:
        workbook.close()


def test_supplier_conversion_output_matches_current_template_layout() -> None:
    filename = "供应商配置.xlsx"
    definition = get_template_definition(filename)
    headers = [str(item) for item in definition.get("headers") or []]
    path = REPO_ROOT / "templates_excel" / "转换输出" / filename
    rows = _read_workbook_rows(path, headers)

    workbook = load_workbook(path, data_only=True)
    try:
        ws = workbook.active
        assert [ws.cell(1, col_idx).value for col_idx in range(1, len(headers) + 1)] == headers
        _assert_layout_matches_definition(ws, definition, filename)
        assert rows, "供应商配置转换输出至少要保留一行转换结果"
        for row in rows:
            assert row[4] in ("启用", "停用")
    finally:
        workbook.close()
