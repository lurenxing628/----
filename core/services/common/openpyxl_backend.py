import os
from typing import List, Dict, Any, Optional

import openpyxl

from core.infrastructure.errors import AppError, ErrorCode
from .tabular_backend import TabularBackend


class OpenpyxlBackend(TabularBackend):
    """V1 Excel 后端：只依赖 openpyxl；对外仅收发 List[Dict]。"""

    def read(self, file_path: str, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb[sheet] if sheet else wb.active

            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []

            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            result: List[Dict[str, Any]] = []

            for raw in rows[1:]:
                # 跳过空行
                if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                    continue

                item: Dict[str, Any] = {}
                for idx, key in enumerate(headers):
                    if not key:
                        continue
                    val = raw[idx] if idx < len(raw) else None
                    if isinstance(val, str):
                        val = val.strip()
                        if val == "":
                            val = None
                    item[key] = val
                result.append(item)

            return result
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.EXCEL_READ_ERROR,
                message="读取 Excel 文件失败，请确认文件未损坏且未被其他程序占用。",
                details={"file_path": file_path, "sheet": sheet},
                cause=e,
            )

    def write(self, rows: List[Dict[str, Any]], file_path: str, sheet: str = "Sheet1"):
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
            )

