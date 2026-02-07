from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .gantt_range import WeekRange


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-")
    if not s:
        return None
    s = s.replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _fmt_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _split_by_day(start_dt: datetime, end_dt: datetime) -> List[Tuple[date, datetime, datetime]]:
    """
    将区间按“自然日”切分，返回 (日期, 片段开始, 片段结束)。
    约定：start_dt < end_dt。
    """
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


def _display_machine(machine_id: Optional[str], machine_name: Optional[str], supplier_name: Optional[str] = None) -> str:
    mid = (machine_id or "").strip()
    if mid:
        name = (machine_name or "").strip()
        return f"{mid} {name}".strip()
    sup = (supplier_name or "").strip()
    return f"外协 {sup}".strip() if sup else "外协/未分配"


def _display_operator(operator_id: Optional[str], operator_name: Optional[str]) -> str:
    oid = (operator_id or "").strip()
    if not oid:
        return "外协/未分配"
    name = (operator_name or "").strip()
    return f"{oid} {name}".strip()


def build_week_plan_rows(*, rows: Sequence[Dict[str, Any]], wr: WeekRange) -> List[Dict[str, Any]]:
    """
    生成周计划行（用于页面预览与导出）。

    字段：日期/批次号/图号/工序/设备/人员/时段
    """
    out: List[Dict[str, Any]] = []
    for r in rows:
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et or not (st < et):
            continue

        st2 = max(st, wr.start_dt)
        et2 = min(et, wr.end_dt_exclusive)
        if not (st2 < et2):
            continue

        machine_disp = _display_machine(r.get("machine_id"), r.get("machine_name"), r.get("supplier_name"))
        operator_disp = _display_operator(r.get("operator_id"), r.get("operator_name"))
        machine_cell = machine_disp if (r.get("machine_id") or "").strip() else "-"
        operator_cell = operator_disp if (r.get("operator_id") or "").strip() else "-"

        parts = _split_by_day(st2, et2)
        for d0, a0, b0 in parts:
            out.append(
                {
                    "日期": d0.isoformat(),
                    "批次号": r.get("batch_id") or "",
                    "图号": r.get("part_no") or "",
                    "工序": r.get("seq") if r.get("seq") is not None else "",
                    "设备": machine_cell,
                    "人员": operator_cell,
                    "时段": f"{_fmt_hhmm(a0)}-{_fmt_hhmm(b0)}",
                }
            )

    out.sort(key=lambda x: (x.get("日期") or "", x.get("设备") or "", x.get("人员") or "", x.get("批次号") or "", x.get("工序") or ""))
    return out

