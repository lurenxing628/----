from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from core.services.scheduler.calendar_service import CalendarService

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


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _priority_class(priority: Optional[str]) -> str:
    p = (priority or "normal").strip() or "normal"
    if p not in ("normal", "urgent", "critical"):
        p = "normal"
    return f"priority-{p}"


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


def build_calendar_days(conn, *, wr: WeekRange, logger=None, op_logger=None) -> List[Dict[str, Any]]:
    """
    当前显示区间的工作日历（用于前端标注假期/停工）。

    说明：
    - 使用 CalendarService.get()：兼容“未配置则按周末默认假期”的规则，也兼容调休补班（手工将周末配成 workday）
    - 任意异常返回空数组（避免甘特图整页 500）
    """
    calendar_days: List[Dict[str, Any]] = []
    try:
        cal_svc = CalendarService(conn, logger=logger, op_logger=op_logger)
        d0 = wr.week_start_date
        while d0 <= wr.week_end_date:
            cal = cal_svc.get(d0.isoformat())
            day_type = str(getattr(cal, "day_type", "") or "")
            try:
                shift_hours = float(getattr(cal, "shift_hours", 0.0) or 0.0)
            except Exception:
                shift_hours = 0.0
            allow_normal = str(getattr(cal, "allow_normal", "") or "")
            allow_urgent = str(getattr(cal, "allow_urgent", "") or "")
            remark = getattr(cal, "remark", None)

            is_holiday = (day_type or "") != "workday"
            is_nonworking = bool(shift_hours <= 0 or (allow_normal == "no" and allow_urgent == "no"))

            calendar_days.append(
                {
                    "date": d0.isoformat(),
                    "day_type": day_type,
                    "shift_hours": shift_hours,
                    "allow_normal": allow_normal,
                    "allow_urgent": allow_urgent,
                    "remark": remark,
                    "is_holiday": is_holiday,
                    "is_nonworking": is_nonworking,
                }
            )
            d0 = d0 + timedelta(days=1)
    except Exception:
        calendar_days = []
    return calendar_days


def build_tasks(
    *,
    view: str,
    wr: WeekRange,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> List[Dict[str, Any]]:
    """
    构建甘特 tasks（供 Frappe Gantt 渲染）。
    """
    tasks: List[Dict[str, Any]] = []
    for r in rows:
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et or not (st < et):
            continue

        # clamp 到本周范围（避免跨周任务把时间轴拉很长）
        st2 = max(st, wr.start_dt)
        et2 = min(et, wr.end_dt_exclusive)
        if not (st2 < et2):
            continue

        op_code = (r.get("op_code") or "").strip()
        task_id = op_code or f"op_{r.get('op_id')}"
        batch_id = (r.get("batch_id") or "").strip()

        machine_disp = _display_machine(r.get("machine_id"), r.get("machine_name"), r.get("supplier_name"))
        operator_disp = _display_operator(r.get("operator_id"), r.get("operator_name"))

        if view == "machine":
            name = f"{task_id} {machine_disp} {operator_disp}".strip()
            group_key = (r.get("machine_id") or "").strip() or "外协/未分配"
        else:
            name = f"{task_id} {operator_disp} {machine_disp}".strip()
            group_key = (r.get("operator_id") or "").strip() or "外协/未分配"

        css = [_priority_class(r.get("priority"))]
        is_overdue = bool(batch_id and batch_id in overdue_set)
        if is_overdue:
            css.append("overdue")

        tasks.append(
            {
                "id": task_id,
                "name": name,
                "start": _fmt_dt(st2),
                "end": _fmt_dt(et2),
                "progress": 0,
                "dependencies": "",
                "custom_class": " ".join(css),
                # 附加信息（前端可用于 tooltip / 调试，不影响 Frappe Gantt）
                "meta": {
                    "op_id": r.get("op_id"),
                    "batch_id": batch_id,
                    "piece_id": r.get("piece_id"),
                    "part_no": r.get("part_no"),
                    "seq": r.get("seq"),
                    "op_type_name": r.get("op_type_name"),
                    "source": r.get("source"),
                    "status": r.get("op_status"),
                    "machine_id": r.get("machine_id"),
                    "operator_id": r.get("operator_id"),
                    "machine": machine_disp,
                    "operator": operator_disp,
                    "group_key": group_key,
                    "priority": r.get("priority"),
                    "due_date": r.get("due_date"),
                    "is_overdue": is_overdue,
                },
            }
        )

    # 工艺依赖：同 (batch_id, piece_id) 的 seq 链（仅在本次 tasks 集合内连线，避免跨窗口缺失）
    chains: Dict[Tuple[str, str], List[Tuple[int, Dict[str, Any]]]] = {}
    for t in tasks:
        meta = t.get("meta") or {}
        bid = str(meta.get("batch_id") or "").strip()
        if not bid:
            continue
        piece_id = str(meta.get("piece_id") or "").strip()
        seq_raw = meta.get("seq")
        try:
            seq_int = int(seq_raw) if seq_raw is not None and str(seq_raw).strip() != "" else 0
        except Exception:
            seq_int = 0
        chains.setdefault((bid, piece_id), []).append((seq_int, t))

    for _, items in chains.items():
        items.sort(key=lambda x: (int(x[0]), str(x[1].get("start") or ""), str(x[1].get("id") or "")))
        prev_id: Optional[str] = None
        for _, t in items:
            tid = str(t.get("id") or "").strip()
            if prev_id and tid:
                # Frappe Gantt：dependencies 为逗号分隔的 task.id 字符串
                t["dependencies"] = prev_id
            if tid:
                prev_id = tid

    # 排序：让同一资源尽量聚在一起（视觉上更像“设备/人员视图”）
    def _sort_key(t: Dict[str, Any]):
        meta = t.get("meta") or {}
        return (str(meta.get("group_key") or ""), str(t.get("start") or ""), str(t.get("id") or ""))

    tasks.sort(key=_sort_key)
    return tasks

