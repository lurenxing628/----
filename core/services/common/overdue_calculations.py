from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.shared.local_datetime import parse_local_datetime


def due_exclusive(due_dt: Optional[date]) -> datetime:
    if due_dt is None:
        return datetime.max
    if isinstance(due_dt, date) and not isinstance(due_dt, datetime):
        due_date = due_dt
    else:
        due_date = due_dt.date()
    if due_date == date.max:
        # 9999-12-31 是 ERP 常见的“无交期”哨兵值（date.max）：再 +1 天会溢出
        # OverflowError。这里显式定义其语义为“最晚”，与 None→datetime.max 合同同向。
        return datetime.max
    return datetime(due_date.year, due_date.month, due_date.day) + timedelta(days=1)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _invalid_time_item(row: Dict[str, Any], *, due_s: Any, as_of: str, now0: datetime, due_excl: datetime, invalid_time_count: int) -> Dict[str, Any]:
    delay_sec = (now0 - due_excl).total_seconds()
    return {
        "bucket": "schedule_time_invalid",
        "bucket_label": "排程时间异常",
        "is_scheduled": True,
        "as_of_time": as_of,
        "batch_id": row.get("batch_id"),
        "part_no": row.get("part_no"),
        "part_name": row.get("part_name"),
        "quantity": row.get("quantity"),
        "due_date": due_s,
        "finish_time": None,
        "delay_hours": round(delay_sec / 3600.0, 2),
        "delay_days": round(delay_sec / 86400.0, 2),
        "invalid_time_count": invalid_time_count or 1,
        "data_issue_message": "有排程记录，但计划完成时间写法不对，不能当作未排程或准时完成。",
    }


def _invalid_due_date_item(row: Dict[str, Any], *, due_s: Any, as_of: str, invalid_time_count: int) -> Dict[str, Any]:
    return {
        "bucket": "due_date_invalid",
        "bucket_label": "交期写法异常",
        "is_scheduled": False,
        "as_of_time": as_of,
        "batch_id": row.get("batch_id"),
        "part_no": row.get("part_no"),
        "part_name": row.get("part_name"),
        "quantity": row.get("quantity"),
        "due_date": due_s,
        "finish_time": row.get("finish_time"),
        "delay_hours": None,
        "delay_days": None,
        "invalid_time_count": invalid_time_count,
        "invalid_due_count": 1,
        "data_issue_message": "批次交期写法不对，系统不能判断它是否超期，请先修正交期。",
    }


def compute_overdue_bucket_groups(
    rows: List[Dict[str, Any]],
    *,
    now_dt: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    now0 = now_dt or datetime.now()
    as_of = now0.strftime("%Y-%m-%d %H:%M:%S")

    scheduled: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []
    invalid_time: List[Dict[str, Any]] = []

    for row in rows:
        due_s = row.get("due_date")
        finish_s = row.get("finish_time")
        invalid_time_count = _int_value(row.get("invalid_time_count"))
        schedule_row_count = _int_value(row.get("schedule_row_count"))
        due_d = parse_local_datetime(due_s)
        if not due_d:
            invalid_time.append(_invalid_due_date_item(row, due_s=due_s, as_of=as_of, invalid_time_count=invalid_time_count))
            continue
        due_excl = due_exclusive(due_d)

        finish_dt = parse_local_datetime(finish_s)
        if finish_dt is not None:
            if finish_dt < due_excl:
                continue
            delay_sec = (finish_dt - due_excl).total_seconds()
            scheduled.append(
                {
                    "bucket": "scheduled_overdue",
                    "bucket_label": "已排程逾期",
                    "is_scheduled": True,
                    "as_of_time": finish_s,
                    "batch_id": row.get("batch_id"),
                    "part_no": row.get("part_no"),
                    "part_name": row.get("part_name"),
                    "quantity": row.get("quantity"),
                    "due_date": due_s,
                    "finish_time": finish_s,
                    "delay_hours": round(delay_sec / 3600.0, 2),
                    "delay_days": round(delay_sec / 86400.0, 2),
                }
            )
            continue

        if invalid_time_count > 0 or (schedule_row_count > 0 and finish_s is not None):
            if now0 < due_excl:
                continue
            invalid_time.append(_invalid_time_item(row, due_s=due_s, as_of=as_of, now0=now0, due_excl=due_excl, invalid_time_count=invalid_time_count))
            continue

        if now0 < due_excl:
            continue
        delay_sec = (now0 - due_excl).total_seconds()
        unscheduled.append(
            {
                "bucket": "unscheduled_overdue",
                "bucket_label": "未排程逾期",
                "is_scheduled": False,
                "as_of_time": as_of,
                "batch_id": row.get("batch_id"),
                "part_no": row.get("part_no"),
                "part_name": row.get("part_name"),
                "quantity": row.get("quantity"),
                "due_date": due_s,
                "finish_time": None,
                "delay_hours": round(delay_sec / 3600.0, 2),
                "delay_days": round(delay_sec / 86400.0, 2),
            }
        )

    return scheduled, unscheduled, invalid_time, as_of
