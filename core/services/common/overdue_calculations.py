from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.date_parsers import due_exclusive
from core.shared.local_datetime import parse_local_datetime


def _overdue_item(
    row: Dict[str, Any],
    *,
    bucket: str,
    bucket_label: str,
    is_scheduled: bool,
    as_of_time: Any,
    due_date: Any,
    finish_time: Any = None,
    delay_sec: Optional[float] = None,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "bucket": bucket,
        "bucket_label": bucket_label,
        "is_scheduled": is_scheduled,
        "as_of_time": as_of_time,
        "batch_id": row.get("batch_id"),
        "part_no": row.get("part_no"),
        "part_name": row.get("part_name"),
        "quantity": row.get("quantity"),
        "due_date": due_date,
        "finish_time": finish_time,
        "delay_hours": round(delay_sec / 3600.0, 2) if delay_sec is not None else None,
        "delay_days": round(delay_sec / 86400.0, 2) if delay_sec is not None else None,
        **extra,
    }


def compute_overdue_bucket_groups(
    rows: List[Dict[str, Any]],
    *,
    now_dt: datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    as_of = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    scheduled: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []
    invalid_time: List[Dict[str, Any]] = []

    for row in rows:
        due_s = row["due_date"]
        finish_s = row["finish_time"]
        invalid_time_count = row.get("invalid_time_count", 0)
        due_d = parse_local_datetime(due_s)
        if not due_d:
            invalid_time.append(
                _overdue_item(
                    row,
                    bucket="due_date_invalid",
                    bucket_label="交期写法异常",
                    is_scheduled=False,
                    as_of_time=as_of,
                    due_date=due_s,
                    finish_time=finish_s,
                    invalid_time_count=invalid_time_count,
                    invalid_due_count=1,
                    data_issue_message="批次交期写法不对，系统不能判断它是否超期，请先修正交期。",
                )
            )
            continue
        due_excl = due_exclusive(due_d)

        finish_dt = parse_local_datetime(finish_s)
        if finish_dt is not None:
            if finish_dt < due_excl:
                continue
            scheduled.append(
                _overdue_item(
                    row,
                    bucket="scheduled_overdue",
                    bucket_label="已排程逾期",
                    is_scheduled=True,
                    as_of_time=finish_s,
                    due_date=due_s,
                    finish_time=finish_s,
                    delay_sec=(finish_dt - due_excl).total_seconds(),
                )
            )
            continue

        if invalid_time_count > 0:
            if now_dt < due_excl:
                continue
            invalid_time.append(
                _overdue_item(
                    row,
                    bucket="schedule_time_invalid",
                    bucket_label="排程时间异常",
                    is_scheduled=True,
                    as_of_time=as_of,
                    due_date=due_s,
                    delay_sec=(now_dt - due_excl).total_seconds(),
                    invalid_time_count=invalid_time_count,
                    data_issue_message="有排程记录，但计划完成时间写法不对，不能当作未排程或准时完成。",
                )
            )
            continue

        if now_dt < due_excl:
            continue
        unscheduled.append(
            _overdue_item(
                row,
                bucket="unscheduled_overdue",
                bucket_label="未排程逾期",
                is_scheduled=False,
                as_of_time=as_of,
                due_date=due_s,
                delay_sec=(now_dt - due_excl).total_seconds(),
            )
        )

    return scheduled, unscheduled, invalid_time
