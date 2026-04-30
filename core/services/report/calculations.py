from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

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


def due_exclusive(due_dt: Optional[datetime]) -> datetime:
    if due_dt is None:
        return datetime.max
    if isinstance(due_dt, date) and not isinstance(due_dt, datetime):
        d = due_dt
    else:
        d = due_dt.date()
    return datetime(d.year, d.month, d.day) + timedelta(days=1)


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


def compute_overdue_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scheduled, unscheduled, _as_of = compute_overdue_buckets(rows)
    # 保持旧接口：items 依然返回列表（已排程在前，未排程在后）
    return list(scheduled) + list(unscheduled)


def compute_overdue_buckets(
    rows: List[Dict[str, Any]],
    *,
    now_dt: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    计算“已排程逾期 / 未排程逾期”两类清单。

    返回：(scheduled_items, unscheduled_items, as_of_time_str)
    - scheduled：有 finish_time 且 finish_time >= due_exclusive
    - unscheduled：无 finish_time 且 now >= due_exclusive（以 now 作为截至时间）
    """
    now0 = now_dt or datetime.now()
    as_of = now0.strftime("%Y-%m-%d %H:%M:%S")

    scheduled: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []

    for r in rows:
        due_s = r.get("due_date")
        finish_s = r.get("finish_time")
        due_d = parse_dt(due_s)
        if not due_d:
            continue
        due_excl = due_exclusive(due_d)

        finish_dt = parse_dt(finish_s)
        if finish_dt is not None:
            # 已排程：按实际完工时间判断
            if finish_dt < due_excl:
                continue
            delay_sec = (finish_dt - due_excl).total_seconds()
            delay_hours = round(delay_sec / 3600.0, 2)
            delay_days = round(delay_sec / 86400.0, 2)
            scheduled.append(
                {
                    "bucket": "scheduled_overdue",
                    "bucket_label": "已排程逾期",
                    "is_scheduled": True,
                    "as_of_time": finish_s,
                    "batch_id": r.get("batch_id"),
                    "part_no": r.get("part_no"),
                    "part_name": r.get("part_name"),
                    "quantity": r.get("quantity"),
                    "due_date": due_s,
                    "finish_time": finish_s,
                    "delay_hours": delay_hours,
                    "delay_days": delay_days,
                }
            )
            continue

        # 未排程：以 now 作为截至时间判断是否逾期
        if now0 < due_excl:
            continue
        delay_sec = (now0 - due_excl).total_seconds()
        delay_hours = round(delay_sec / 3600.0, 2)
        delay_days = round(delay_sec / 86400.0, 2)
        unscheduled.append(
            {
                "bucket": "unscheduled_overdue",
                "bucket_label": "未排程逾期",
                "is_scheduled": False,
                "as_of_time": as_of,
                "batch_id": r.get("batch_id"),
                "part_no": r.get("part_no"),
                "part_name": r.get("part_name"),
                "quantity": r.get("quantity"),
                "due_date": due_s,
                "finish_time": None,
                "delay_hours": delay_hours,
                "delay_days": delay_days,
            }
        )

    return scheduled, unscheduled, as_of
