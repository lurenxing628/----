from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint

from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx
from .normalizers import _normalize_operator_calendar_day_type, _normalize_yesno

bp = Blueprint("personnel", __name__)


def _operator_status_zh(status: str) -> str:
    if status == "active":
        return "在岗"
    if status == "inactive":
        return "停用/休假"
    return status or "-"


def _machine_status_zh(status: str) -> str:
    if status == "active":
        return "可用"
    if status == "maintain":
        return "维修"
    if status == "inactive":
        return "停用"
    return status or "-"


def _day_type_zh(day_type: str) -> str:
    """
    日历类型中文展示：
    - workday：工作日
    - holiday/weekend：假期
    """
    v = (day_type or "").strip()
    if v == "workday":
        return "工作日"
    if v in ("holiday", "weekend"):
        return "假期"
    return v or "-"


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)

