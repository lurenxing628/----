from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx
from .normalizers import _normalize_batch_priority, _normalize_day_type, _normalize_ready_status, _normalize_yesno


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


# -------------------------
# 批次 Excel 标准化
# -------------------------
def _normalize_due_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().replace("/", "-")
        return v if v else None
    # datetime/date
    try:
        return value.date().isoformat() if hasattr(value, "date") else str(value)
    except Exception:
        return str(value)


# -------------------------
# 日历 Excel 标准化
# -------------------------
def _normalize_calendar_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().replace("/", "-")
    try:
        # datetime/date
        return value.date().isoformat() if hasattr(value, "date") else str(value)
    except Exception:
        return str(value)

