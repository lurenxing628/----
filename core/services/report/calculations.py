from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError
from core.models.enums import SourceType


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


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def due_exclusive(due_dt: Optional[datetime]) -> datetime:
    if due_dt is None:
        return datetime.max
    if isinstance(due_dt, date) and not isinstance(due_dt, datetime):
        d = due_dt
    else:
        d = due_dt.date()
    return datetime(d.year, d.month, d.day) + timedelta(days=1)


def overlap_seconds(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if e <= s:
        return 0.0
    return float((e - s).total_seconds())


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


def compute_utilization(
    *,
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
    cap_hours: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_machine: Dict[str, Dict[str, Any]] = {}
    by_operator: Dict[str, Dict[str, Any]] = {}

    for r in schedule_rows:
        if (r.get("source") or "").strip().lower() != SourceType.INTERNAL.value:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt:
            continue
        sec = overlap_seconds(s_dt, e_dt, start_dt, end_dt_excl)
        if sec <= 0:
            continue
        hours = sec / 3600.0

        mc = (r.get("machine_id") or "").strip()
        if mc:
            it = by_machine.setdefault(
                mc,
                {"machine_id": mc, "machine_name": r.get("machine_name"), "hours": 0.0, "task_count": 0},
            )
            it["hours"] = float(it["hours"]) + float(hours)
            it["task_count"] = int(it["task_count"]) + 1

        op = (r.get("operator_id") or "").strip()
        if op:
            it = by_operator.setdefault(
                op,
                {"operator_id": op, "operator_name": r.get("operator_name"), "hours": 0.0, "task_count": 0},
            )
            it["hours"] = float(it["hours"]) + float(hours)
            it["task_count"] = int(it["task_count"]) + 1

    machine_rows = []
    for it in by_machine.values():
        h = float(it["hours"])
        util = (h / cap_hours) if cap_hours > 0 else None
        machine_rows.append(
            {
                **it,
                "hours": round(h, 2),
                "capacity_hours": round(cap_hours, 2),
                "utilization": round(util, 4) if util is not None else None,
            }
        )
    machine_rows.sort(key=lambda x: (-(x.get("hours") or 0.0), x.get("machine_id") or ""))

    operator_rows = []
    for it in by_operator.values():
        h = float(it["hours"])
        util = (h / cap_hours) if cap_hours > 0 else None
        operator_rows.append(
            {
                **it,
                "hours": round(h, 2),
                "capacity_hours": round(cap_hours, 2),
                "utilization": round(util, 4) if util is not None else None,
            }
        )
    operator_rows.sort(key=lambda x: (-(x.get("hours") or 0.0), x.get("operator_id") or ""))

    return machine_rows, operator_rows


def compute_downtime_impact(
    *,
    downtime_rows: List[Dict[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
) -> List[Dict[str, Any]]:
    by_machine_dt: Dict[str, List[Tuple[datetime, datetime, str, str]]] = {}
    machine_name: Dict[str, Any] = {}
    for r in downtime_rows:
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt:
            continue
        by_machine_dt.setdefault(mc, []).append((s_dt, e_dt, str(r.get("reason_code") or ""), str(r.get("reason_detail") or "")))
        if mc not in machine_name:
            machine_name[mc] = r.get("machine_name")

    by_machine_sch: Dict[str, List[Tuple[datetime, datetime]]] = {}
    for r in schedule_rows:
        if (r.get("source") or "").strip().lower() != SourceType.INTERNAL.value:
            continue
        mc = str(r.get("machine_id") or "").strip()
        if not mc:
            continue
        s_dt = parse_dt(r.get("start_time"))
        e_dt = parse_dt(r.get("end_time"))
        if not s_dt or not e_dt:
            continue
        by_machine_sch.setdefault(mc, []).append((s_dt, e_dt))

    items: List[Dict[str, Any]] = []
    for mc, dts in by_machine_dt.items():
        downtime_sec = 0.0
        for ds, de, _, _ in dts:
            downtime_sec += overlap_seconds(ds, de, start_dt, end_dt_excl)

        overlap_sec = 0.0
        impact_count = 0
        segs = by_machine_sch.get(mc) or []
        for ds, de, _, _ in dts:
            for ss, se in segs:
                sec = overlap_seconds(ds, de, ss, se)
                if sec > 0:
                    overlap_sec += sec
                    impact_count += 1

        items.append(
            {
                "machine_id": mc,
                "machine_name": machine_name.get(mc),
                "downtime_hours": round(downtime_sec / 3600.0, 2),
                "downtime_count": len(dts),
                "schedule_overlap_hours": round(overlap_sec / 3600.0, 2),
                "schedule_overlap_count": int(impact_count),
            }
        )

    items.sort(key=lambda x: (-(x.get("downtime_hours") or 0.0), x.get("machine_id") or ""))
    return items
