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
    scheduled, unscheduled, invalid_time, _as_of = compute_overdue_bucket_groups(rows)
    return list(scheduled) + list(invalid_time) + list(unscheduled)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _invalid_time_item(row: Dict[str, Any], *, due_s: Any, as_of: str, now0: datetime, due_excl: datetime) -> Dict[str, Any]:
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
        "invalid_time_count": _int_value(row.get("invalid_time_count")) or 1,
        "data_issue_message": "有排程记录，但计划完成时间写法不对，不能当作未排程或准时完成。",
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

        if invalid_time_count > 0 or (schedule_row_count > 0 and finish_s is not None):
            if now0 < due_excl:
                continue
            invalid_time.append(_invalid_time_item(row, due_s=due_s, as_of=as_of, now0=now0, due_excl=due_excl))
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


def compute_overdue_buckets(
    rows: List[Dict[str, Any]],
    *,
    now_dt: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    scheduled, unscheduled, _invalid_time, as_of = compute_overdue_bucket_groups(rows, now_dt=now_dt)
    return scheduled, unscheduled, as_of


def collect_bad_time_rows(rows: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """统计所有批次（含已排程/准时/未排程）的坏时间行总数与样本批次号。

    诚实展示的关键：不能只数“排程时间异常”桶。一个批次只要有一条有效完成时间，就会进
    已排程/准时分支，但它仍可能夹带坏时间行（部分工序时间写法不对）——这些坏行不计入跨度、
    此前也不计入任何降级提示，属于“消除静默却残留的静默”。这里按批次行聚合的
    invalid_time_count 汇总全部坏行，让混合批次的不完整也能被用户看见。
    """
    total = 0
    samples: List[str] = []
    for row in rows:
        bad = _int_value(row.get("invalid_time_count"))
        if bad <= 0:
            continue
        total += bad
        batch_id = row.get("batch_id")
        if batch_id:
            samples.append(f"批次号={batch_id}")
    return total, samples
