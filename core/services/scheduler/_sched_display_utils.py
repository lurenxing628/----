from __future__ import annotations

from datetime import date, datetime, time, timedelta
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
    op_code = str(row.get("op_code") or "").strip()
    if op_code:
        parts.append(f"工序编码={op_code}")
    batch_id = str(row.get("batch_id") or "").strip()
    if batch_id:
        parts.append(f"批次号={batch_id}")
    bad_fields: List[str] = []
    if row.get("start_time") is not None and parse_dt(row.get("start_time")) is None:
        bad_fields.append("开始时间")
    if row.get("end_time") is not None and parse_dt(row.get("end_time")) is None:
        bad_fields.append("结束时间")
    parts.append(f"字段={'、'.join(bad_fields) if bad_fields else '开始时间或结束时间'}")
    return " / ".join(parts) if parts else None


def record_bad_time_row(
    collector: DegradationCollector,
    *,
    scope: str,
    row: Dict[str, Any],
    message: str = "存在开始或结束时间写法不对的排程行，已跳过。",
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


def fmt_day_segment(start_dt: datetime, end_dt: datetime) -> str:
    start_text = fmt_hhmm(start_dt)
    is_exact_next_midnight = (
        end_dt.date() > start_dt.date()
        and end_dt.hour == 0
        and end_dt.minute == 0
        and end_dt.second == 0
        and end_dt.microsecond == 0
    )
    end_text = "24:00" if is_exact_next_midnight else fmt_hhmm(end_dt)
    return "全天" if start_text == "00:00" and end_text == "24:00" else f"{start_text}-{end_text}"


_NOON = time(12, 0)


def capacity_hours_at_noon(calendar: Any, day: Any) -> float:
    """单日单资源容量：正午采样的 shift_hours×efficiency；休息日（shift_hours≤0）为 0。

    4.6 共享协议唯一实现（周计划 day_totals 与甘特负荷条带共用）——刻意不调
    calculations.capacity_hours（midnight 采样在跨午夜班次错归属，4.6 红线）。
    """
    policy = calendar.policy_for_datetime(datetime.combine(day, _NOON))
    shift_hours = float(getattr(policy, "shift_hours", 0.0) or 0.0)
    if shift_hours <= 0:
        return 0.0
    return shift_hours * float(getattr(policy, "efficiency", 1.0) or 1.0)


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
