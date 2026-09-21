"""转换输出用的 XLSX 写盘，以及导出单元格的公式净化。

2026-09 退役了启动期生成 templates_excel/ 旧模板那一套（ensure_excel_templates 与随之而来的
旧模板表头/布局修复）：12 张业务表的模板改由工作台按表描述现生成，不再预先摆一份文件在磁盘上。
这里只剩两件还在用的事：转换输出子系统的 build_xlsx_bytes + get_template_definition，
以及各家族导出共用的 sanitize_export_cell。
"""

from __future__ import annotations

import io
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .excel_template_defaults import get_default_templates


def _close_workbook_quietly(wb: Any) -> None:
    try:
        wb.close()
    except Exception:
        return


def _active_sheet_or_none(wb: Any) -> Any:
    try:
        return wb.active
    except (AttributeError, IndexError, KeyError):
        return None


def _require_active_sheet(wb: Any) -> Any:
    ws = _active_sheet_or_none(wb)
    if ws is None:
        raise ValueError("Workbook 缺少活动工作表")
    return ws


def sanitize_export_cell(value: Any) -> Any:
    if isinstance(value, str):
        value = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\t\n\r")
        if value and value[0] in ("=", "+", "-", "@"):
            return "'" + value
    return value


_sanitize_export_cell = sanitize_export_cell


def _iter_column_indices(spec: Mapping[str, Any], key: str) -> Iterable[int]:
    for col_idx in spec.get(key, []) or []:
        if isinstance(col_idx, int) and col_idx >= 0:
            yield col_idx


def _apply_number_format(ws, col_indices: Iterable[int], fmt: str, max_row: int) -> None:
    for col_idx in col_indices:
        col_letter = get_column_letter(col_idx + 1)
        for row_idx in range(2, max_row + 1):
            ws[f"{col_letter}{row_idx}"].number_format = fmt


def _apply_enum_validations(ws, enum_cols: Mapping[int, Sequence[str]], max_row: int) -> None:
    for col_idx, values in (enum_cols or {}).items():
        if not isinstance(col_idx, int) or col_idx < 0:
            continue
        items = [str(v).strip() for v in (values or []) if str(v).strip()]
        if not items:
            continue
        dv = DataValidation(type="list", formula1=f"\"{','.join(items)}\"", allow_blank=True)
        col_letter = get_column_letter(col_idx + 1)
        dv.add(f"{col_letter}2:{col_letter}{max_row}")
        ws.add_data_validation(dv)


def _auto_width(ws, *, explicit_widths: Optional[Mapping[int, int]] = None) -> None:
    widths: Dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            text = "" if cell.value is None else str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), len(text))
    for col_idx, content_width in widths.items():
        width = min(max(content_width + 2, 12), 36)
        if explicit_widths and (col_idx - 1) in explicit_widths:
            width = max(width, int(explicit_widths[col_idx - 1]))
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    if explicit_widths:
        for zero_based_idx, width in explicit_widths.items():
            ws.column_dimensions[get_column_letter(int(zero_based_idx) + 1)].width = max(
                ws.column_dimensions[get_column_letter(int(zero_based_idx) + 1)].width or 0,
                int(width),
            )


def _apply_sheet_layout(
    ws,
    *,
    format_spec: Optional[Mapping[str, Any]],
    data_row_count: int,
) -> None:
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    spec = format_spec or {}
    max_row = max(int(data_row_count) + 200, 500)
    _apply_number_format(ws, _iter_column_indices(spec, "text_cols"), "@", max_row)
    _apply_number_format(ws, _iter_column_indices(spec, "int_cols"), "0", max_row)
    _apply_number_format(ws, _iter_column_indices(spec, "float_cols"), "0.00", max_row)
    _apply_number_format(ws, _iter_column_indices(spec, "date_cols"), "yyyy-mm-dd", max_row)
    _apply_number_format(ws, _iter_column_indices(spec, "time_cols"), "hh:mm", max_row)
    # 这里的工作表一定来自 build_xlsx_bytes 新建的工作簿，不可能带着旧的下拉规则，
    # 所以不再先清理再挂——清理那一套是给已退役的旧模板修复路径用的。
    _apply_enum_validations(ws, spec.get("enum_cols", {}) or {}, max_row)
    _auto_width(ws, explicit_widths=spec.get("column_widths", {}) or {})


def build_xlsx_bytes(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]] = (),
    *,
    format_spec: Optional[Mapping[str, Any]] = None,
    sheet_title: str = "Sheet1",
    sanitize_formula: bool = False,
) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = _require_active_sheet(wb)
        ws.title = sheet_title
        ws.append(list(headers))
        for r in rows:
            row_values = [_sanitize_export_cell(v) if sanitize_formula else v for v in r]
            ws.append(list(row_values))
        _apply_sheet_layout(ws, format_spec=format_spec, data_row_count=len(rows))
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    finally:
        _close_workbook_quietly(wb)


def get_template_definition(filename: str) -> Dict[str, Any]:
    for item in get_default_templates():
        if str(item.get("filename")) == str(filename):
            return item
    raise KeyError(f"unknown template: {filename}")
