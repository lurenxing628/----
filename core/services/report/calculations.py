from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from core.infrastructure.errors import ValidationError
from core.services.common.overdue_calculations import compute_overdue_buckets, compute_overdue_items, due_exclusive

from .calculation_helpers import overlap_seconds, parse_dt
from .downtime_impact import compute_downtime_impact as _compute_downtime_impact
from .utilization import compute_utilization as _compute_utilization


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows,
    start_dt: datetime,
    end_dt_excl: datetime,
) -> List[Dict[str, Any]]:
    return _compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )


def compute_utilization(
    *,
    schedule_rows,
    start_dt: datetime,
    end_dt_excl: datetime,
    cap_hours: float,
):
    return _compute_utilization(
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=cap_hours,
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


def capacity_hours(calendar: Any, start_d: date, end_d: date) -> float:
    """
    以“日历的工作窗 * efficiency”作为单资源可用工时（简化：不区分设备/人员差异）。
    """
    total = 0.0
    cur = start_d
    while cur <= end_d:
        p = calendar.policy_for_datetime(datetime.combine(cur, datetime.min.time()))
        if float(getattr(p, "shift_hours", 0.0) or 0.0) > 0:
            total += float(getattr(p, "shift_hours", 0.0) or 0.0) * float(getattr(p, "efficiency", 1.0) or 1.0)
        cur = cur + timedelta(days=1)
    return float(round(total, 6))
