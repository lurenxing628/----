from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from core.models.enums import CalendarDayType, YesNo
from core.services.scheduler.calendar_service import CalendarService

from ._sched_utils import _safe_int
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


def _duration_minutes(st: datetime, et: datetime) -> int:
    delta = (et - st).total_seconds()
    if delta <= 0:
        return 0
    return int(delta // 60)


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

            is_holiday = (day_type or "") != CalendarDayType.WORKDAY.value
            is_nonworking = bool(
                shift_hours <= 0 or (allow_normal == YesNo.NO.value and allow_urgent == YesNo.NO.value)
            )

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


def _clamp_to_week(st: datetime, et: datetime, *, wr: WeekRange) -> Optional[Tuple[datetime, datetime]]:
    # clamp 到本周范围（避免跨周任务把时间轴拉很长）
    st2 = max(st, wr.start_dt)
    et2 = min(et, wr.end_dt_exclusive)
    if not (st2 < et2):
        return None
    return st2, et2


def _task_name_and_group(
    *,
    view: str,
    task_id: str,
    machine_disp: str,
    operator_disp: str,
    machine_id: Optional[str],
    operator_id: Optional[str],
) -> Tuple[str, str]:
    if view == "machine":
        name = f"{task_id} {machine_disp} {operator_disp}".strip()
        group_key = (machine_id or "").strip() or "外协/未分配"
    else:
        name = f"{task_id} {operator_disp} {machine_disp}".strip()
        group_key = (operator_id or "").strip() or "外协/未分配"
    return name, group_key


def _build_one_task(
    *,
    view: str,
    wr: WeekRange,
    r: Dict[str, Any],
    overdue_set: Set[str],
) -> Optional[Dict[str, Any]]:
    st = _parse_dt(r.get("start_time"))
    et = _parse_dt(r.get("end_time"))
    if not st or not et or not (st < et):
        return None

    clamped = _clamp_to_week(st, et, wr=wr)
    if not clamped:
        return None
    st2, et2 = clamped

    op_code = (r.get("op_code") or "").strip()
    task_id = op_code or f"op_{r.get('op_id')}"
    batch_id = (r.get("batch_id") or "").strip()

    machine_disp = _display_machine(r.get("machine_id"), r.get("machine_name"), r.get("supplier_name"))
    operator_disp = _display_operator(r.get("operator_id"), r.get("operator_name"))
    name, group_key = _task_name_and_group(
        view=view,
        task_id=task_id,
        machine_disp=machine_disp,
        operator_disp=operator_disp,
        machine_id=r.get("machine_id"),
        operator_id=r.get("operator_id"),
    )

    css = [_priority_class(r.get("priority"))]
    is_overdue = bool(batch_id and batch_id in overdue_set)
    if is_overdue:
        css.append("overdue")

    duration = _duration_minutes(st2, et2)
    return {
        "id": task_id,
        "schedule_id": r.get("schedule_id"),
        "name": name,
        "start": _fmt_dt(st2),
        "end": _fmt_dt(et2),
        "duration_minutes": duration,
        "progress": 0,
        "lock_status": r.get("lock_status"),
        "dependencies": "",
        "edge_type": "",
        "custom_class": " ".join(css),
        # 附加信息（前端可用于 tooltip / 调试，不影响 Frappe Gantt）
        "meta": {
            "schedule_id": r.get("schedule_id"),
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
            "lock_status": r.get("lock_status"),
            "duration_minutes": duration,
            "due_date": r.get("due_date"),
            "is_overdue": is_overdue,
        },
    }


def _attach_process_dependencies(tasks: List[Dict[str, Any]]) -> None:
    # 工艺依赖：同 (batch_id, piece_id) 的 seq 链（仅在本次 tasks 集合内连线，避免跨窗口缺失）
    chains: Dict[Tuple[str, str], List[Tuple[int, Dict[str, Any]]]] = {}
    for t in tasks:
        meta = t.get("meta") or {}
        bid = str(meta.get("batch_id") or "").strip()
        if not bid:
            continue
        piece_id = str(meta.get("piece_id") or "").strip()
        seq_int = _safe_int(meta.get("seq"), default=0)
        chains.setdefault((bid, piece_id), []).append((seq_int, t))

    for _, items in chains.items():
        items.sort(key=lambda x: (int(x[0]), str(x[1].get("start") or ""), str(x[1].get("id") or "")))
        prev_id: Optional[str] = None
        for _, t in items:
            tid = str(t.get("id") or "").strip()
            if not tid:
                continue
            if prev_id:
                # Frappe Gantt：dependencies 为逗号分隔的 task.id 字符串
                t["dependencies"] = prev_id
                t["edge_type"] = "process"
                t_meta = t.get("meta")
                if isinstance(t_meta, dict):
                    t_meta["edge_type"] = "process"
                    t_meta["dependency_from"] = prev_id
            prev_id = tid


def _sort_tasks(tasks: List[Dict[str, Any]]) -> None:
    # 排序：让同一资源尽量聚在一起（视觉上更像“设备/人员视图”）
    def _sort_key(t: Dict[str, Any]):
        meta = t.get("meta") or {}
        return (str(meta.get("group_key") or ""), str(t.get("start") or ""), str(t.get("id") or ""))

    tasks.sort(key=_sort_key)


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
        t = _build_one_task(view=view, wr=wr, r=dict(r), overdue_set=overdue_set)
        if t:
            tasks.append(t)

    _attach_process_dependencies(tasks)
    _sort_tasks(tasks)
    return tasks

