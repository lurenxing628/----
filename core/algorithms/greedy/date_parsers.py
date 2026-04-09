from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 0, 0, 0)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


def due_exclusive(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    return datetime(d.year, d.month, d.day, 0, 0, 0) + timedelta(days=1)
