from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint

from core.services.common.excel_service import ImportMode

from .enum_display import day_type_zh, machine_status_zh, operator_status_zh
from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx
from .normalizers import _normalize_operator_calendar_day_type, _normalize_yesno

bp = Blueprint("personnel", __name__)


def _operator_status_zh(status: str) -> str:
    return operator_status_zh(status)


def _machine_status_zh(status: str) -> str:
    return machine_status_zh(status)


def _day_type_zh(day_type: str) -> str:
    return day_type_zh(day_type)


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)

