from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint

from core.services.common.excel_service import ImportMode

from .enum_display import machine_status_zh, operator_status_zh
from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx

bp = Blueprint("equipment", __name__)


def _machine_status_zh(status: str) -> str:
    return machine_status_zh(status)


def _operator_status_zh(status: str) -> str:
    return operator_status_zh(status)


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)

