from __future__ import annotations

from datetime import date, datetime, timedelta
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
    cap_hours: float,
    degradation_collector=None,
):
    return _compute_utilization(
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=cap_hours,
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


def capacity_hours(calendar: Any, start_d: date, end_d: date) -> float:
    """
    累计工作窗与自然日范围的交集 * efficiency（仍不区分设备/人员差异）。
    """
    total = 0.0
    cur = datetime.combine(start_d, datetime.min.time())
    end_dt_excl = datetime.combine(end_d, datetime.min.time()) + timedelta(days=1)
    while cur < end_dt_excl:
        p = calendar.policy_for_datetime(cur)
        window_start, window_end = p.work_window()
        if float(getattr(p, "shift_hours", 0.0) or 0.0) > 0:
            hours = overlap_seconds(window_start, window_end, cur, end_dt_excl) / 3600.0
            total += hours * float(getattr(p, "efficiency", 1.0) or 1.0)
        # 跨夜窗结束后重新取策略，不能直接跳到次日而漏掉同日后续班次。
        if window_end > cur:
            cur = window_end
        else:
            cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time())
    return float(round(total, 6))
