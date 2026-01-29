from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint

from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx


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


def _normalize_operator_calendar_day_type(value: Any) -> str:
    """
    人员专属日历类型标准化：
    - workday/工作日 -> workday
    - holiday/假期/节假日 -> holiday
    - weekend/周末 -> holiday（统一口径）
    """
    v = "" if value is None else str(value).strip()
    if v in ("工作日", "workday"):
        return "workday"
    if v in ("周末", "weekend"):
        return "holiday"
    if v in ("节假日", "假期", "holiday"):
        return "holiday"
    return v or "workday"


def _normalize_yesno(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("是", "y", "Y", "yes", "YES"):
        return "yes"
    if v in ("否", "n", "N", "no", "NO"):
        return "no"
    return v or "yes"


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)

