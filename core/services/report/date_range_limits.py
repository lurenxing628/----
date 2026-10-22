from __future__ import annotations

from datetime import date
from typing import Any

from core.errors import ValidationError

REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS = 62


def ensure_report_date_range_within_limit(
    start_date: date,
    end_date: date,
    *,
    field: Any = "date_range",
) -> None:
    day_count = (end_date - start_date).days + 1
    if day_count > REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS:
        raise ValidationError(f"日期范围不能超过 {REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS} 天", field=field)
