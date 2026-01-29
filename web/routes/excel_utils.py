from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ImportMode


def parse_import_mode(value: str) -> ImportMode:
    """
    解析导入模式（字符串 -> ImportMode）。
    - 保持与各模块历史行为一致：非法值统一抛 ValidationError
    """
    try:
        return ImportMode(value)
    except Exception:
        raise ValidationError("导入模式不合法", field="mode")


def ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    """
    Excel 主键去重校验：
    - 行内该列为空则跳过
    - 存在重复则抛 ValidationError（文案保持稳定）
    """
    seen = set()
    dup = set()
    for r in rows:
        v = r.get(id_column)
        if v is None:
            continue
        key = str(v).strip()
        if not key:
            continue
        if key in seen:
            dup.add(key)
        seen.add(key)
    if dup:
        sample = ", ".join(list(sorted(dup))[:10])
        raise ValidationError(f"Excel 中存在重复的“{id_column}”：{sample}。请去重后再导入。", field=id_column)


def read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    """
    把上传的 Excel（.xlsx）解析为 List[Dict]（key 为表头字符串）。
    - 跳过空行
    - 单元格字符串自动 strip；空串视为 None
    - 统一走 backend.read(file_path)，以支持可选 pandas 后端
    """
    data = file_storage.read()
    if not data:
        raise AppError(ErrorCode.EXCEL_FORMAT_ERROR, "上传文件为空，请重新选择。")

    fd, tmp_path = tempfile.mkstemp(prefix="aps_upload_", suffix=".xlsx")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        backend = get_excel_backend()
        return backend.read(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

