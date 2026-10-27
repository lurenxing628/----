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
    except ValueError:
        return None


def due_exclusive(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    if (d.year, d.month, d.day) == (date.max.year, date.max.month, date.max.day):
        # 9999-12-31 是 ERP 常见的“无交期”哨兵值（date.max 的日期）：再 +1 天会溢出
        # OverflowError。这里显式定义其语义为“最晚”，与 None→datetime.max 合同同向。
        return datetime.max
    return datetime(d.year, d.month, d.day, 0, 0, 0) + timedelta(days=1)
