from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from core.models.enums import CalendarDayType, YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector
from core.services.scheduler.calendar_service import CalendarService

from ._sched_display_utils import (
    BAD_TIME_EMPTY_REASON as _BAD_TIME_EMPTY_REASON,
)
from ._sched_display_utils import (
    display_machine as _display_machine,
)
from ._sched_display_utils import (
    display_operator as _display_operator,
)
from ._sched_display_utils import (
    duration_minutes as _duration_minutes,
)
from ._sched_display_utils import (
    fmt_dt as _fmt_dt,
)
from ._sched_display_utils import (
    parse_dt as _parse_dt,
)
from ._sched_display_utils import (
    priority_class as _priority_class,
)
from ._sched_display_utils import (
    record_bad_time_row as _record_bad_time_row,
)
from ._sched_utils import _safe_int
from .gantt_range import WeekRange

_CALENDAR_LOAD_EMPTY_REASON = "calendar_load_failed"



def build_calendar_days(conn, *, wr: WeekRange, logger=None, op_logger=None) -> BuildOutcome[List[Dict[str, Any]]]:
    """
    当前显示区间的工作日历（用于前端标注假期/停工）。

    说明：
    - 使用 CalendarService.get()：兼容“未配置则按周末默认假期”的规则，也兼容调休补班（手工将周末配成 workday）
    - 任意异常返回空数组（避免甘特图整页 500），并透出统一退化事件
    """
    calendar_days: List[Dict[str, Any]] = []
    collector = DegradationCollector()
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
    except Exception as exc:
        collector.add(
            code="calendar_load_failed",
            scope="gantt.calendar_days",
            field="calendar_days",
            message="工作日历加载失败，已降级为空列表。",
            sample=exc.__class__.__name__,
        )
        return BuildOutcome.from_collector(calendar_days, collector, empty_reason=_CALENDAR_LOAD_EMPTY_REASON)
    return BuildOutcome.from_collector(calendar_days, collector)


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
    row: Mapping[str, Any],
    overdue_set: Set[str],
) -> BuildOutcome[Optional[Dict[str, Any]]]:
    collector = DegradationCollector()
    st = _parse_dt(row.get("start_time"))
    et = _parse_dt(row.get("end_time"))
    if not st or not et or not (st < et):
        _record_bad_time_row(collector, scope="gantt.tasks", row=dict(row))
        return BuildOutcome.from_collector(None, collector)

    clamped = _clamp_to_week(st, et, wr=wr)
    if not clamped:
        return BuildOutcome.from_collector(None, collector)
    st2, et2 = clamped

    op_code = (row.get("op_code") or "").strip()
    task_id = op_code or f"op_{row.get('op_id')}"
    batch_id = (row.get("batch_id") or "").strip()

    machine_disp = _display_machine(row.get("machine_id"), row.get("machine_name"), row.get("supplier_name"))
    operator_disp = _display_operator(row.get("operator_id"), row.get("operator_name"))
    name, group_key = _task_name_and_group(
        view=view,
        task_id=task_id,
        machine_disp=machine_disp,
        operator_disp=operator_disp,
        machine_id=row.get("machine_id"),
        operator_id=row.get("operator_id"),
    )

    css = [_priority_class(row.get("priority"))]
    is_overdue = bool(batch_id and batch_id in overdue_set)
    if is_overdue:
        css.append("overdue")

    duration = _duration_minutes(st2, et2)
    task = {
        "id": task_id,
        "schedule_id": row.get("schedule_id"),
        "name": name,
        "start": _fmt_dt(st2),
        "end": _fmt_dt(et2),
        "duration_minutes": duration,
        "progress": 0,
        "lock_status": row.get("lock_status"),
        "dependencies": "",
        "edge_type": "",
        "custom_class": " ".join(css),
        # 附加信息（前端可用于 tooltip / 调试，不影响 Frappe Gantt）
        "meta": {
            "schedule_id": row.get("schedule_id"),
            "op_id": row.get("op_id"),
            "batch_id": batch_id,
            "piece_id": row.get("piece_id"),
            "part_no": row.get("part_no"),
            "seq": row.get("seq"),
            "op_type_name": row.get("op_type_name"),
            "source": row.get("source"),
            "status": row.get("op_status"),
            "machine_id": row.get("machine_id"),
            "operator_id": row.get("operator_id"),
            "machine": machine_disp,
            "operator": operator_disp,
            "group_key": group_key,
            "priority": row.get("priority"),
            "lock_status": row.get("lock_status"),
            "duration_minutes": duration,
            "due_date": row.get("due_date"),
            "is_overdue": is_overdue,
        },
    }
    return BuildOutcome.from_collector(task, collector)


def _attach_process_dependencies(tasks: List[Dict[str, Any]]) -> None:
    # 工艺依赖：同 (batch_id, piece_id) 的 seq 链（仅在本次 tasks 集合内连线，避免跨窗口缺失）
    chains: Dict[Tuple[str, str], List[Tuple[int, Dict[str, Any]]]] = {}
    for task in tasks:
        meta = task.get("meta") or {}
        bid = str(meta.get("batch_id") or "").strip()
        if not bid:
            continue
        piece_id = str(meta.get("piece_id") or "").strip()
        seq_int = _safe_int(meta.get("seq"), default=0)
        chains.setdefault((bid, piece_id), []).append((seq_int, task))

    for _, items in chains.items():
        items.sort(key=lambda item: (int(item[0]), str(item[1].get("start") or ""), str(item[1].get("id") or "")))
        prev_id: Optional[str] = None
        for _, task in items:
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue
            if prev_id:
                # Frappe Gantt：dependencies 为逗号分隔的 task.id 字符串
                task["dependencies"] = prev_id
                task["edge_type"] = "process"
                task_meta = task.get("meta")
                if isinstance(task_meta, dict):
                    task_meta["edge_type"] = "process"
                    task_meta["dependency_from"] = prev_id
            prev_id = task_id


def _sort_tasks(tasks: List[Dict[str, Any]]) -> None:
    # 排序：让同一资源尽量聚在一起（视觉上更像“设备/人员视图”）
    def _sort_key(task: Dict[str, Any]):
        meta = task.get("meta") or {}
        return (str(meta.get("group_key") or ""), str(task.get("start") or ""), str(task.get("id") or ""))

    tasks.sort(key=_sort_key)


def build_tasks(
    *,
    view: str,
    wr: WeekRange,
    rows: Sequence[Mapping[str, Any]],
    overdue_set: Set[str],
) -> BuildOutcome[List[Dict[str, Any]]]:
    """
    构建甘特 tasks（供 Frappe Gantt 渲染）。
    """
    collector = DegradationCollector()
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        outcome = _build_one_task(view=view, wr=wr, row=row, overdue_set=overdue_set)
        collector.extend(outcome.events)
        if outcome.value is not None:
            tasks.append(outcome.value)

    _attach_process_dependencies(tasks)
    _sort_tasks(tasks)
    empty_reason = None
    if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(tasks, collector, empty_reason=empty_reason)
