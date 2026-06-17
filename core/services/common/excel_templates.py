from __future__ import annotations

import io
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from core.infrastructure.safe_files import read_fixed_bytes, write_fixed_bytes

from .excel_template_defaults import get_default_templates


class ExcelTemplateError(RuntimeError):
    """Excel 模板文件不可安全读取或修复。"""


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
    enum_cols = spec.get("enum_cols", {}) or {}
    _remove_enum_validations(ws, enum_cols)
    _apply_enum_validations(ws, enum_cols, max_row)
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


def _write_xlsx(
    path: str,
    headers: Sequence[str],
    sample_rows: Sequence[Sequence[Any]] = (),
    *,
    format_spec: Optional[Mapping[str, Any]] = None,
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    output = build_xlsx_bytes(headers, sample_rows, format_spec=format_spec)
    write_fixed_bytes(path, output.getvalue())


def _load_fixed_workbook(path: str, *, data_only: bool = False) -> Any:
    return openpyxl.load_workbook(io.BytesIO(read_fixed_bytes(path)), data_only=data_only)


def _save_fixed_workbook(wb: Any, path: str) -> None:
    output = io.BytesIO()
    wb.save(output)
    write_fixed_bytes(path, output.getvalue())


def _read_xlsx_headers(path: str) -> List[str]:
    try:
        # 不用 read_only：read_only 懒加载在 Windows 上即便 close() 也可能不立即释放底层归档句柄，
        # 导致调用方临时目录清理报 PermissionError[WinError 32]。模板文件很小，普通模式一次性读入、
        # close() 同步释放句柄；data_only 取缓存值即可读表头文本。
        wb = _load_fixed_workbook(path, data_only=True)
    except Exception as exc:
        raise ExcelTemplateError(f"读取 Excel 模板表头失败：{os.path.basename(path)}") from exc
    try:
        ws = _require_active_sheet(wb)
        first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not first_row:
            return []
        return ["" if value is None else str(value).strip() for value in first_row]
    except ExcelTemplateError:
        raise
    except Exception as exc:
        raise ExcelTemplateError(f"读取 Excel 模板首行失败：{os.path.basename(path)}") from exc
    finally:
        _close_workbook_quietly(wb)


_LEGACY_TEMPLATE_ENUM_VALUES: Set[str] = {
    "active",
    "inactive",
    "maintain",
    "internal",
    "external",
    "内部",
    "外部",
    "beginner",
    "normal",
    "expert",
    "urgent",
    "critical",
    "partial",
    "workday",
    "holiday",
    "yes",
    "no",
}

_EXTRA_ROW_LAYOUT_REPAIR_TEMPLATES: Set[str] = {
    "工种配置.xlsx",
}


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _row_has_value(row: Sequence[Any]) -> bool:
    return any(_cell_text(value) for value in row)


def _inline_validation_values(formula: Any) -> List[str]:
    text = _cell_text(formula)
    if len(text) < 2 or not (text.startswith('"') and text.endswith('"')):
        return []
    return [item.strip() for item in text[1:-1].split(",") if item.strip()]


def _non_empty_data_rows(ws: Any) -> List[Sequence[Any]]:
    return [row for row in ws.iter_rows(min_row=2, values_only=True) if _row_has_value(row)]


def _enum_texts_from_row(row: Sequence[Any], enum_col_indices: Iterable[int]) -> Set[str]:
    texts: Set[str] = set()
    for col_idx in enum_col_indices:
        if col_idx >= len(row):
            continue
        text = _cell_text(row[col_idx]).lower()
        if text:
            texts.add(text)
    return texts


def _enum_texts_from_rows(rows: Iterable[Sequence[Any]], enum_col_indices: Iterable[int]) -> Set[str]:
    texts: Set[str] = set()
    for row in rows:
        texts.update(_enum_texts_from_row(row, enum_col_indices))
    return texts


def _inline_validation_texts(ws: Any) -> Set[str]:
    texts: Set[str] = set()
    for dv in getattr(ws.data_validations, "dataValidation", []) or []:
        for value in _inline_validation_values(getattr(dv, "formula1", "")):
            texts.add(value.lower())
    return texts


def _cell_range_ref(min_col: int, min_row: int, max_col: int, max_row: int) -> str:
    start = f"{get_column_letter(min_col)}{min_row}"
    end = f"{get_column_letter(max_col)}{max_row}"
    return start if start == end else f"{start}:{end}"


def _range_refs_without_columns(cell_range: Any, removed_columns: Set[int]) -> List[str]:
    if cell_range.max_row < 2 or not any(cell_range.min_col <= col <= cell_range.max_col for col in removed_columns):
        return [str(cell_range)]

    refs: List[str] = []
    run_start: Optional[int] = None
    for col_idx in range(cell_range.min_col, cell_range.max_col + 1):
        if col_idx in removed_columns:
            if run_start is not None:
                refs.append(_cell_range_ref(run_start, cell_range.min_row, col_idx - 1, cell_range.max_row))
                run_start = None
            continue
        if run_start is None:
            run_start = col_idx
    if run_start is not None:
        refs.append(_cell_range_ref(run_start, cell_range.min_row, cell_range.max_col, cell_range.max_row))
    return refs


def _remove_enum_validations(ws: Any, enum_col_indices: Iterable[int]) -> None:
    validation_list = getattr(getattr(ws, "data_validations", None), "dataValidation", None)
    if validation_list is None:
        return
    enum_columns = {col_idx + 1 for col_idx in enum_col_indices if isinstance(col_idx, int) and col_idx >= 0}
    if not enum_columns:
        return
    kept_validations = []
    for dv in validation_list:
        if getattr(dv, "type", None) != "list":
            kept_validations.append(dv)
            continue
        kept_ranges: List[str] = []
        for cell_range in getattr(getattr(dv, "sqref", None), "ranges", []) or []:
            kept_ranges.extend(_range_refs_without_columns(cell_range, enum_columns))
        if kept_ranges:
            dv.sqref = " ".join(kept_ranges)
            kept_validations.append(dv)
    ws.data_validations.dataValidation = kept_validations


def _template_layout_repair_plan(template_def: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if str(template_def.get("filename") or "") not in _EXTRA_ROW_LAYOUT_REPAIR_TEMPLATES:
        return None
    format_spec = template_def.get("format_spec", {}) or {}
    enum_col_indices = set(format_spec.get("enum_cols", {}) or {})
    if not enum_col_indices:
        return None
    return {
        "format_spec": format_spec,
        "enum_col_indices": enum_col_indices,
        "sample_row_count": len(template_def.get("sample_rows") or []),
        "headers": [str(header).strip() for header in (template_def.get("headers") or [])],
    }


def _current_headers(ws: Any, header_count: int) -> List[str]:
    return [_cell_text(ws.cell(1, col_idx).value) for col_idx in range(1, header_count + 1)]


def _trim_trailing_blank_headers(headers: Sequence[Any]) -> List[str]:
    out = [_cell_text(value) for value in headers]
    while out and not out[-1]:
        out.pop()
    return out


def _current_header_row(ws: Any) -> List[str]:
    return _trim_trailing_blank_headers([cell.value for cell in ws[1]])


def _template_needs_layout_repair(ws: Any, repair_plan: Mapping[str, Any]) -> bool:
    non_empty_data_rows = _non_empty_data_rows(ws)
    headers = list(repair_plan["headers"])
    if _current_header_row(ws) != headers:
        return False
    enum_texts = _enum_texts_from_rows(non_empty_data_rows, repair_plan["enum_col_indices"])
    enum_texts.update(_inline_validation_texts(ws))
    return bool(enum_texts & _LEGACY_TEMPLATE_ENUM_VALUES)


def _rewrite_template_headers(ws: Any, headers: Sequence[str]) -> None:
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(1, col_idx).value = header


def _legacy_header_sets(template_def: Mapping[str, Any]) -> List[List[str]]:
    header_sets: List[List[str]] = []
    for headers in template_def.get("legacy_headers", []) or []:
        normalized = [str(header).strip() for header in (headers or [])]
        if normalized:
            header_sets.append(normalized)
    return header_sets


def _refresh_existing_template_headers(path: str, template_def: Mapping[str, Any]) -> bool:
    expected_headers = [str(header).strip() for header in (template_def.get("headers") or [])]
    legacy_header_sets = _legacy_header_sets(template_def)
    if not expected_headers or not legacy_header_sets:
        return False
    try:
        wb = _load_fixed_workbook(path)
    except Exception as exc:
        raise ExcelTemplateError(f"打开待修复 Excel 模板失败：{os.path.basename(path)}") from exc
    try:
        ws = _require_active_sheet(wb)
        if _current_header_row(ws) not in legacy_header_sets:
            return False
        _rewrite_template_headers(ws, expected_headers)
        _apply_sheet_layout(ws, format_spec=template_def.get("format_spec"), data_row_count=ws.max_row - 1)
        _save_fixed_workbook(wb, path)
        return True
    except ExcelTemplateError:
        raise
    except Exception as exc:
        raise ExcelTemplateError(f"修复 Excel 模板表头失败：{os.path.basename(path)}") from exc
    finally:
        _close_workbook_quietly(wb)


def _refresh_existing_template_layout(path: str, template_def: Mapping[str, Any]) -> bool:
    repair_plan = _template_layout_repair_plan(template_def)
    if repair_plan is None:
        return False
    try:
        wb = _load_fixed_workbook(path)
    except Exception as exc:
        raise ExcelTemplateError(f"打开待修复 Excel 模板失败：{os.path.basename(path)}") from exc
    try:
        ws = _require_active_sheet(wb)

        if not _template_needs_layout_repair(ws, repair_plan):
            return False

        _rewrite_template_headers(ws, repair_plan["headers"])
        _remove_enum_validations(ws, repair_plan["enum_col_indices"])
        _apply_sheet_layout(ws, format_spec=repair_plan["format_spec"], data_row_count=ws.max_row - 1)
        _save_fixed_workbook(wb, path)
        return True
    except ExcelTemplateError:
        raise
    except Exception as exc:
        raise ExcelTemplateError(f"修复 Excel 模板布局失败：{os.path.basename(path)}") from exc
    finally:
        _close_workbook_quietly(wb)


def _known_generated_template_needs_refresh(path: str, template_def: Mapping[str, Any]) -> bool:
    """Refresh old generated templates that still expose raw enum defaults.

    The guard is intentionally narrow: if a workbook contains user data beyond the
    built-in sample rows, keep it untouched unless that template has a known
    safe in-place layout repair.
    """
    format_spec = template_def.get("format_spec", {}) or {}
    enum_col_indices = set(format_spec.get("enum_cols", {}) or {})
    if not enum_col_indices:
        return False

    sample_row_count = len(template_def.get("sample_rows") or [])
    can_repair_extra_rows = str(template_def.get("filename") or "") in _EXTRA_ROW_LAYOUT_REPAIR_TEMPLATES
    try:
        wb = _load_fixed_workbook(path, data_only=True)
    except Exception as exc:
        raise ExcelTemplateError(f"检查 Excel 模板是否需要刷新失败：{os.path.basename(path)}") from exc
    try:
        ws = _require_active_sheet(wb)

        non_empty_data_rows = _non_empty_data_rows(ws)
        if len(non_empty_data_rows) > sample_row_count and not can_repair_extra_rows:
            return False
        enum_texts = _enum_texts_from_rows(non_empty_data_rows, enum_col_indices)
        enum_texts.update(_inline_validation_texts(ws))

        return bool(enum_texts & _LEGACY_TEMPLATE_ENUM_VALUES)
    except ExcelTemplateError:
        raise
    except Exception as exc:
        raise ExcelTemplateError(f"检查 Excel 模板枚举值失败：{os.path.basename(path)}") from exc
    finally:
        _close_workbook_quietly(wb)


def get_template_definition(filename: str) -> Dict[str, Any]:
    for item in get_default_templates():
        if str(item.get("filename")) == str(filename):
            return item
    raise KeyError(f"unknown template: {filename}")


def ensure_excel_templates(template_dir: str) -> Dict[str, Any]:
    """
    确保 templates_excel 目录下存在所有交付模板文件。
    - 若文件存在则不覆盖（避免用户手工修改被覆盖）
    - 若文件存在但表头与当前真源不一致，则按当前真源重建
    - 若目录为空/缺失，则补齐
    """
    template_dir = os.path.abspath(template_dir or "templates_excel")
    os.makedirs(template_dir, exist_ok=True)

    created: List[str] = []
    skipped: List[str] = []

    for t in get_default_templates():
        filename = t["filename"]
        path = os.path.join(template_dir, filename)
        expected_headers = [str(header).strip() for header in (t.get("headers") or [])]
        if os.path.exists(path):
            actual_headers = _read_xlsx_headers(path)
            if actual_headers == expected_headers:
                if not _known_generated_template_needs_refresh(path, t):
                    skipped.append(filename)
                    continue
                if _refresh_existing_template_layout(path, t):
                    created.append(filename)
                    continue
                raise ExcelTemplateError(f"已有 Excel 模板内容需要刷新，但不能安全自动覆盖：{filename}")
            if actual_headers in _legacy_header_sets(t) and _refresh_existing_template_headers(path, t):
                created.append(filename)
                continue
            raise ExcelTemplateError(f"已有 Excel 模板表头和当前定义不一致，不能自动覆盖：{filename}")

        _write_xlsx(path, headers=t["headers"], sample_rows=t.get("sample_rows") or [], format_spec=t.get("format_spec"))
        created.append(filename)

    return {"template_dir": template_dir, "created": created, "skipped": skipped}
