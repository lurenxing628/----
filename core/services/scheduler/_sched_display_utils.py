from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.services.common.degradation import DegradationCollector

BAD_TIME_EMPTY_REASON = "all_rows_filtered_by_invalid_time"


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("/", "-")
    if not text:
        return None
    text = text.replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def duration_minutes(st: datetime, et: datetime) -> int:
    delta = (et - st).total_seconds()
    if delta <= 0:
        return 0
    return int(delta // 60)


def priority_class(priority: Optional[str]) -> str:
    text = (priority or "normal").strip() or "normal"
    if text not in ("normal", "urgent", "critical"):
        text = "normal"
    return f"priority-{text}"


def display_machine(machine_id: Optional[str], machine_name: Optional[str], supplier_name: Optional[str] = None) -> str:
    mid = (machine_id or "").strip()
    if mid:
        name = (machine_name or "").strip()
        return f"{mid} {name}".strip()
    supplier = (supplier_name or "").strip()
    return f"外协 {supplier}".strip() if supplier else "外协/未分配"


def display_operator(operator_id: Optional[str], operator_name: Optional[str]) -> str:
    oid = (operator_id or "").strip()
    if not oid:
        return "外协/未分配"
    name = (operator_name or "").strip()
    return f"{oid} {name}".strip()


def bad_time_row_sample(row: Dict[str, Any]) -> Optional[str]:
    parts: List[str] = []
    if row.get("schedule_id") is not None:
        parts.append(f"排程记录编号={row.get('schedule_id')}")
    if row.get("op_id") is not None:
        parts.append(f"工序编号={row.get('op_id')}")
    batch_id = str(row.get("batch_id") or "").strip()
    if batch_id:
        parts.append(f"批次号={batch_id}")
    if row.get("start_time") is not None:
        parts.append(f"start_time={row.get('start_time')}")
    if row.get("end_time") is not None:
        parts.append(f"end_time={row.get('end_time')}")
    return " / ".join(parts) if parts else None


def record_bad_time_row(
    collector: DegradationCollector,
    *,
    scope: str,
    row: Dict[str, Any],
    message: str = "存在开始/结束时间不合法的排程行，已跳过。",
) -> None:
    collector.add(
        code="bad_time_row_skipped",
        scope=scope,
        field="time_range",
        message=message,
        sample=bad_time_row_sample(row),
    )


def fmt_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def split_by_day(start_dt: datetime, end_dt: datetime) -> List[Tuple[date, datetime, datetime]]:
    cur = start_dt
    out: List[Tuple[date, datetime, datetime]] = []
    while cur.date() < end_dt.date():
        day_end = datetime(cur.year, cur.month, cur.day) + timedelta(days=1)
        if cur < day_end:
            out.append((cur.date(), cur, day_end))
        cur = day_end
    if cur < end_dt:
        out.append((cur.date(), cur, end_dt))
    return out
