from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from core.errors import ValidationError
from core.shared.stored_dates import stored_day

_OPTIONAL_ISO_DATETIME_RE = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})(?:([T ])((?:[01][0-9]|2[0-3]):[0-5][0-9])(?::([0-5][0-9])(?:\.([0-9]{1,6}))?)?)?\Z"
)


def parse_date(value: Any) -> Optional[date]:
    """A day the algorithm takes: a date, or the stored ``YYYY-MM-DD`` text; None for anything else.

    Run admission already rejects every other spelling, so slashes, unpadded digits and whitespace are not repaired here.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return stored_day(value) if type(value) is str else None


def require_optional_date(value: Any, *, field: str) -> Optional[date]:
    if value is None:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError(f"“{field}”格式不合法（期望：YYYY-MM-DD）", field=field)
    return parsed


def require_optional_datetime(value: Any, *, field: str) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if type(value) is date:
        return datetime(value.year, value.month, value.day, 0, 0, 0)
    if type(value) is str:
        matched = _OPTIONAL_ISO_DATETIME_RE.match(value)
        if matched is not None:
            day, _sep, hm, sec, frac = matched.groups()
            iso = f"{day}T{hm or '00:00'}:{sec or '00'}"
            if frac is not None:
                iso = f"{iso}.{frac.ljust(6, '0')}"
            try:
                return datetime.fromisoformat(iso)
            except ValueError as exc:
                raise ValidationError(
                    f"“{field}”格式不合法（期望：YYYY-MM-DD 或 ISO 本地日期时间）",
                    field=field,
                ) from exc
    raise ValidationError(f"“{field}”格式不合法（期望：YYYY-MM-DD 或 ISO 本地日期时间）", field=field)


def due_exclusive(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    if (d.year, d.month, d.day) == (date.max.year, date.max.month, date.max.day):
        # 9999-12-31 是 ERP 常见的“无交期”哨兵值（date.max 的日期）：再 +1 天会溢出
        # OverflowError。这里显式定义其语义为“最晚”，与 None→datetime.max 合同同向。
        return datetime.max
    return datetime(d.year, d.month, d.day, 0, 0, 0) + timedelta(days=1)
