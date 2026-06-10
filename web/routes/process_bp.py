from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint

from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode
from core.services.common.enum_normalizers import source_type_label
from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx

bp = Blueprint("process", __name__)


def _merge_mode_zh(value: str) -> str:
    # R41/O26：enum_normalizers 无 merge_mode 的 canonical 标签函数，保留私有（强建收口点=新 P5，禁）。
    if value == MergeMode.MERGED.value:
        return "合并设置"
    return "分别设置"


def _source_zh(value: str) -> str:
    # R41/O26 收口并顺手修 bug：旧实现「非 external 一律自制」会把中文别名「外协」「外」误判成
    # 「自制」；标准版 source_type_label 先 normalize_op_type_category 再贴标签，别名正确归类，
    # 未知值显示「未知」不再误贴确定态。
    return source_type_label(value)


def _safe_float(value: Any, field: str) -> Optional[float]:
    if value is None:
        return None
    v = str(value).strip()
    if v == "":
        return None
    try:
        return float(v)
    except Exception as e:
        raise ValidationError(f"“{field}”必须是数字", field=field) from e


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)
