from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint

from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx


bp = Blueprint("process", __name__)


def _merge_mode_zh(value: str) -> str:
    if value == "merged":
        return "合并设置"
    return "分别设置"


def _source_zh(value: str) -> str:
    if value == "external":
        return "外部"
    return "内部"


def _safe_float(value: Any, field: str) -> Optional[float]:
    if value is None:
        return None
    v = str(value).strip()
    if v == "":
        return None
    try:
        return float(v)
    except Exception:
        raise ValidationError(f"“{field}”必须是数字", field=field)


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)

