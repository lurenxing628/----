from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from core.infrastructure.errors import ValidationError
from core.services.common.overdue_calculations import (
    collect_bad_time_rows,
    compute_overdue_bucket_groups,
    compute_overdue_buckets,
    compute_overdue_items,
    due_exclusive,
)

from .calculation_helpers import overlap_seconds, parse_dt
from .downtime_impact import compute_downtime_impact as _compute_downtime_impact
from .utilization import compute_utilization as _compute_utilization


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows,
    start_dt: datetime,
    end_dt_excl: datetime,
    degradation_collector=None,
) -> List[Dict[str, Any]]:
    return _compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        degradation_collector=degradation_collector,
    )


def compute_utilization(
    *,
    schedule_rows,
    start_dt: datetime,
    end_dt_excl: datetime,
    calendars,
    degradation_collector=None,
):
    return _compute_utilization(
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        calendars=calendars,
        degradation_collector=degradation_collector,
    )


def parse_date(value: Any, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value or "").strip().replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception as e:
        raise ValidationError("日期格式不合法（期望：YYYY-MM-DD）", field=field) from e
