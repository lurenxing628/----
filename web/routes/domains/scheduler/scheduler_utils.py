from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import g, request

from core.services.common.excel_service import ImportMode

from ...excel_utils import ensure_unique_ids, parse_import_mode, read_uploaded_xlsx
from ...normalizers import _normalize_batch_priority as _normalize_batch_priority_impl
from ...normalizers import _normalize_day_type as _normalize_day_type_impl
from ...normalizers import _normalize_ready_status as _normalize_ready_status_impl
from ...normalizers import _normalize_yesno as _normalize_yesno_impl


def _current_scheduler_operator() -> str:
    operator = str(getattr(g, "scheduler_operator", "") or "").strip()
    return operator or "web"


def get_plan_role_arg() -> Optional[str]:
    # R72 收口:gantt/week_plan 两份 _get_plan_role_arg 的唯一来源。
    # 语义铁律:缺参/空串/空白一律 None(由下游 resolve 决定默认),这里绝不兜底成 ROLE_ADOPTED。
    raw = request.args.get("plan_role")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    ensure_unique_ids(rows, id_column=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    return read_uploaded_xlsx(file_storage)


def _normalize_batch_priority(value: Any) -> str:
    return _normalize_batch_priority_impl(value)


def _normalize_ready_status(value: Any) -> str:
    return _normalize_ready_status_impl(value)


def _normalize_day_type(value: Any) -> str:
    return _normalize_day_type_impl(value)


def _normalize_yesno(value: Any) -> str:
    return _normalize_yesno_impl(value)


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
