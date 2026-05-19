from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def due_exclusive(due_dt: Optional[datetime]) -> datetime:
    if due_dt is None:
        return datetime.max
    if isinstance(due_dt, date) and not isinstance(due_dt, datetime):
        due_date = due_dt
    else:
        due_date = due_dt.date()
    return datetime(due_date.year, due_date.month, due_date.day) + timedelta(days=1)


def compute_overdue_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scheduled, unscheduled, _as_of = compute_overdue_buckets(rows)
    return list(scheduled) + list(unscheduled)


def compute_overdue_buckets(
    rows: List[Dict[str, Any]],
    *,
    now_dt: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    now0 = now_dt or datetime.now()
    as_of = now0.strftime("%Y-%m-%d %H:%M:%S")

    scheduled: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []

    for row in rows:
        due_s = row.get("due_date")
        finish_s = row.get("finish_time")
        due_d = parse_dt(due_s)
        if not due_d:
            continue
        due_excl = due_exclusive(due_d)

        finish_dt = parse_dt(finish_s)
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

    return scheduled, unscheduled, as_of
