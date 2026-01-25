from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import AppError, ErrorCode

from .tabular_backend import TabularBackend


class PandasBackend(TabularBackend):
    """
    可选 Excel 后端：pandas + numpy（读取/写入 xlsx）。

    约束：对外仍只收发 List[Dict]，不暴露 DataFrame。
    """

    def read(self, file_path: str, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            import pandas as pd

            df = pd.read_excel(file_path, sheet_name=sheet or 0, dtype=object)
            # 统一空值
            df = df.where(pd.notnull(df), None)
            raw_rows = df.to_dict(orient="records")

            result: List[Dict[str, Any]] = []
            for r in raw_rows:
                item: Dict[str, Any] = {}
                for k, v in (r or {}).items():
                    key = str(k).strip() if k is not None else ""
                    if not key:
                        continue
                    val = v
                    if isinstance(val, str):
                        val = val.strip()
                        if val == "":
                            val = None
                    item[key] = val
                # 跳过空行
                if not item or all(v is None or (isinstance(v, str) and v.strip() == "") for v in item.values()):
                    continue
                result.append(item)
            return result
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.EXCEL_READ_ERROR,
                message="读取 Excel 文件失败（pandas），请确认文件未损坏且未被其他程序占用。",
                details={"file_path": file_path, "sheet": sheet},
                cause=e,
            )

    def write(self, rows: List[Dict[str, Any]], file_path: str, sheet: str = "Sheet1"):
        try:
            import pandas as pd

            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

            if not rows:
                # 仍生成一个空文件（只有标题行/空表）
                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    pd.DataFrame([]).to_excel(writer, index=False, sheet_name=sheet)
                return

            headers = list(rows[0].keys())
            df = pd.DataFrame(rows)
            # 尽量保持列顺序与首行一致
            try:
                df = df[headers]
            except Exception:
                pass

            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=sheet)
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.EXCEL_WRITE_ERROR,
                message="写入 Excel 文件失败（pandas），请确认目标路径可写。",
                details={"file_path": file_path, "sheet": sheet},
                cause=e,
            )

