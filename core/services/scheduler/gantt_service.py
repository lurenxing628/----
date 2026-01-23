from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError
from data.repositories import ScheduleHistoryRepository, ScheduleRepository


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip().replace("/", "-")
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _split_by_day(start_dt: datetime, end_dt: datetime) -> List[Tuple[date, datetime, datetime]]:
    """
    将区间按“自然日”切分，返回 (日期, 片段开始, 片段结束)。
    约定：start_dt < end_dt。
    """
    cur = start_dt
    out: List[Tuple[date, datetime, datetime]] = []
    while cur.date() < end_dt.date():
        day_end = datetime(cur.year, cur.month, cur.day) + timedelta(days=1)
        out.append((cur.date(), cur, day_end))
        cur = day_end
    out.append((cur.date(), cur, end_dt))
    return out


@dataclass
class WeekRange:
    week_start_date: date
    week_end_date: date  # 周日
    start_dt: datetime  # 周一 00:00:00
    end_dt_exclusive: datetime  # 下周一 00:00:00

    @property
    def start_str(self) -> str:
        return _fmt_dt(self.start_dt)

    @property
    def end_exclusive_str(self) -> str:
        return _fmt_dt(self.end_dt_exclusive)


class GanttService:
    """
    Phase 8：甘特图与周计划服务。

    职责：
    - 按周范围 + version 输出甘特 tasks（供 Frappe Gantt 渲染）
    - 生成周计划表导出行（按天切分时段）
    - 复用 ScheduleHistory.result_summary 的超期信息做标记
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)

    def get_latest_version_or_1(self) -> int:
        v = int(self.history_repo.get_latest_version() or 0)
        return v if v > 0 else 1

    def resolve_week_range(
        self,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> WeekRange:
        """
        计算显示范围：
        - 优先使用 start_date/end_date（区间模式，包含起止日）
        - 否则使用 week_start + offset_weeks（周模式，周一~周日）

        参数：
        - week_start：可选，期望为 YYYY-MM-DD；若不传则以“今天所在周”的周一为起点
        - offset_weeks：周偏移（-1 上周，+1 下周）
        - start_date/end_date：可选，期望为 YYYY-MM-DD；若提供则优先使用
        """
        sd = _parse_date(start_date) if start_date else None
        ed = _parse_date(end_date) if end_date else None
        if sd or ed:
            # 区间模式：默认 start_date=明天；end_date 未填则默认 7 天窗口
            if not sd:
                sd = date.today() + timedelta(days=1)
            if not ed:
                ed = sd + timedelta(days=6)
            if ed < sd:
                raise ValidationError("end_date 不能早于 start_date", field="end_date")

            start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
            end_dt_exclusive = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
            return WeekRange(week_start_date=sd, week_end_date=ed, start_dt=start_dt, end_dt_exclusive=end_dt_exclusive)

        # 周模式
        if week_start:
            d = _parse_date(week_start)
            if not d:
                raise ValidationError("week_start 格式不合法（期望：YYYY-MM-DD）", field="week_start")
            monday = _monday_of(d)
        else:
            # 默认：明天所在周（便于用户“从明天开始看排程”）
            monday = _monday_of(date.today() + timedelta(days=1))

        try:
            offset_weeks_int = int(offset_weeks)
        except Exception:
            raise ValidationError("offset_weeks 不合法（期望整数）", field="offset_weeks")

        monday = monday + timedelta(days=7 * offset_weeks_int)
        sunday = monday + timedelta(days=6)
        start_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
        end_dt_exclusive = start_dt + timedelta(days=7)
        return WeekRange(week_start_date=monday, week_end_date=sunday, start_dt=start_dt, end_dt_exclusive=end_dt_exclusive)

    def _overdue_batch_ids_from_history(self, version: int) -> Sequence[str]:
        hist = self.history_repo.get_by_version(int(version))
        if not hist or not hist.result_summary:
            return []
        try:
            obj = json.loads(hist.result_summary or "{}")
        except Exception:
            return []

        overdue = obj.get("overdue_batches")
        # 兼容两种结构：list 或 {count, items}
        if isinstance(overdue, list):
            return [str(x.get("batch_id")) for x in overdue if isinstance(x, dict) and x.get("batch_id")]
        if isinstance(overdue, dict):
            items = overdue.get("items") or []
            if isinstance(items, list):
                return [str(x.get("batch_id")) for x in items if isinstance(x, dict) and x.get("batch_id")]
        return []

    @staticmethod
    def _priority_class(priority: Optional[str]) -> str:
        p = (priority or "normal").strip() or "normal"
        if p not in ("normal", "urgent", "critical"):
            p = "normal"
        return f"priority-{p}"

    @staticmethod
    def _display_machine(machine_id: Optional[str], machine_name: Optional[str], supplier_name: Optional[str] = None) -> str:
        mid = (machine_id or "").strip()
        if mid:
            name = (machine_name or "").strip()
            return f"{mid} {name}".strip()
        sup = (supplier_name or "").strip()
        return f"外协 {sup}".strip() if sup else "外协/未分配"

    @staticmethod
    def _display_operator(operator_id: Optional[str], operator_name: Optional[str]) -> str:
        oid = (operator_id or "").strip()
        if not oid:
            return "外协/未分配"
        name = (operator_name or "").strip()
        return f"{oid} {name}".strip()

    def get_gantt_tasks(
        self,
        *,
        view: str,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        返回甘特图数据（tasks + 元信息）。
        view：machine / operator
        """
        view = (view or "").strip() or "machine"
        if view not in ("machine", "operator"):
            raise ValidationError("view 不合法（允许：machine/operator）", field="view")

        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        ver = int(version) if version is not None and str(version).strip() != "" else self.get_latest_version_or_1()

        rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exclusive_str, ver)
        overdue_set = set(self._overdue_batch_ids_from_history(ver))

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

            machine_disp = self._display_machine(r.get("machine_id"), r.get("machine_name"), r.get("supplier_name"))
            operator_disp = self._display_operator(r.get("operator_id"), r.get("operator_name"))

            if view == "machine":
                name = f"{task_id} {machine_disp} {operator_disp}".strip()
                group_key = (r.get("machine_id") or "").strip() or "外协/未分配"
            else:
                name = f"{task_id} {operator_disp} {machine_disp}".strip()
                group_key = (r.get("operator_id") or "").strip() or "外协/未分配"

            css = [self._priority_class(r.get("priority"))]
            if batch_id and batch_id in overdue_set:
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
                        "batch_id": batch_id,
                        "part_no": r.get("part_no"),
                        "seq": r.get("seq"),
                        "op_type_name": r.get("op_type_name"),
                        "source": r.get("source"),
                        "machine": machine_disp,
                        "operator": operator_disp,
                        "group_key": group_key,
                        "priority": r.get("priority"),
                        "due_date": r.get("due_date"),
                    },
                }
            )

        # 排序：让同一资源尽量聚在一起（视觉上更像“设备/人员视图”）
        def _sort_key(t: Dict[str, Any]):
            meta = t.get("meta") or {}
            return (str(meta.get("group_key") or ""), str(t.get("start") or ""), str(t.get("id") or ""))

        tasks.sort(key=_sort_key)

        hist = self.history_repo.get_by_version(ver)
        hist_dict = hist.to_dict() if hist else None

        return {
            "view": view,
            "version": ver,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "tasks": tasks,
            "history": hist_dict,
        }

    def get_week_plan_rows(
        self,
        *,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        返回周计划行（用于页面预览与导出）。
        字段：日期/批次号/图号/工序/设备/人员/时段
        """
        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        ver = int(version) if version is not None and str(version).strip() != "" else self.get_latest_version_or_1()

        rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exclusive_str, ver)
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

            machine_disp = self._display_machine(r.get("machine_id"), r.get("machine_name"), r.get("supplier_name"))
            operator_disp = self._display_operator(r.get("operator_id"), r.get("operator_name"))
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
        hist = self.history_repo.get_by_version(ver)
        return {
            "version": ver,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "rows": out,
            "history": hist.to_dict() if hist else None,
        }

