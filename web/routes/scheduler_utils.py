from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.services.common.excel_service import ImportMode

from .excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


# -------------------------
# 批次 Excel 标准化
# -------------------------


def _normalize_batch_priority(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("普通", "normal"):
        return "normal"
    if v in ("急", "急件", "urgent"):
        return "urgent"
    if v in ("特急", "critical"):
        return "critical"
    return v or "normal"


def _normalize_ready_status(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("齐套", "是", "yes"):
        return "yes"
    if v in ("部分齐套", "partial"):
        return "partial"
    if v in ("未齐套", "否", "no"):
        return "no"
    # V1.1：齐套默认视为 yes（可缺省）
    return v or "yes"


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


def _normalize_day_type(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("工作日", "workday"):
        return "workday"
    # 统一：周末本质属于“假期”
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

