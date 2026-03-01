from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import openpyxl

from core.infrastructure.errors import AppError, ErrorCode

from .tabular_backend import TabularBackend


def _normalize_header_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_cell_value(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        return None if s == "" else s
    return value


def _is_blank_cell(value: Any) -> bool:
    if value is None:
        return True
    try:
        return str(value).strip() == ""
    except Exception:
        return False


def _is_blank_row(raw: Any) -> bool:
    if raw is None:
        return True
    return all(_is_blank_cell(v) for v in raw)


def _row_to_item(headers: List[str], raw: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {}
    for idx, key in enumerate(headers):
        if not key:
            continue
        val = raw[idx] if idx < len(raw) else None
        item[key] = _normalize_cell_value(val)
    return item


def _convert_worksheet_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    headers = [_normalize_header_cell(h) for h in rows[0]]
    result: List[Dict[str, Any]] = []

    for raw in rows[1:]:
        # 跳过空行
        if _is_blank_row(raw):
            continue
        result.append(_row_to_item(headers, raw))

    return result


class OpenpyxlBackend(TabularBackend):
    """V1 Excel 后端：只依赖 openpyxl；对外仅收发 List[Dict]。"""

    def read(self, file_path: str, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        wb = None
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb[sheet] if sheet else wb.active

            rows = list(ws.iter_rows(values_only=True))
            return _convert_worksheet_rows(rows)
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.EXCEL_READ_ERROR,
                message="读取 Excel 文件失败，请确认文件未损坏且未被其他程序占用。",
                details={"file_path": file_path, "sheet": sheet},
                cause=e,
            ) from e
        finally:
            try:
                if wb is not None:
                    wb.close()
            except Exception:
                pass

    def write(self, rows: List[Dict[str, Any]], file_path: str, sheet: str = "Sheet1") -> None:
        wb = None
        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet

            if not rows:
                wb.save(file_path)
                return

            headers = list(rows[0].keys())
            ws.append(headers)
            for r in rows:
                ws.append([r.get(h) for h in headers])

            wb.save(file_path)
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.EXCEL_WRITE_ERROR,
                message="写入 Excel 文件失败，请确认目标路径可写。",
                details={"file_path": file_path, "sheet": sheet},
                cause=e,
            ) from e
        finally:
            try:
                if wb is not None:
                    wb.close()
            except Exception:
                pass

