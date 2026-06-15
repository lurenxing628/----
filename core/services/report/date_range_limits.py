from __future__ import annotations

from datetime import date
from typing import Any

from core.infrastructure.errors import ValidationError
from core.services.scheduler.resource_dispatch_range import MAX_DISPATCH_RANGE_DAYS

REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS = MAX_DISPATCH_RANGE_DAYS


def ensure_report_date_range_within_limit(
    start_date: date,
    end_date: date,
    *,
    field: Any = "date_range",
    max_day_count: int = REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS,
) -> None:
    day_count = (end_date - start_date).days + 1
    if day_count <= 0:
        raise ValidationError("日期范围写法不对，请重新选择开始日期和结束日期。", field=field)
    if day_count > int(max_day_count):
        raise ValidationError(f"日期范围不能超过 {int(max_day_count)} 天", field=field)
