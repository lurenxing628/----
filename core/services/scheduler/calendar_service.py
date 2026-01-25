from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import WorkCalendar
from core.models.enums import BatchPriority, CalendarDayType, YesNo
from data.repositories import CalendarRepository


@dataclass
class DayPolicy:
    """
    某天的排产策略（从 WorkCalendar 推导）。

    说明：
    - shift_start 可配置（默认 08:00）
    - shift_hours=0 视为不可排产日
    - allow_normal/allow_urgent 控制普通/急件是否允许排在该日
      - critical 视作 urgent（更严格时可单独扩展字段）
    """

    date_str: str  # YYYY-MM-DD
    day_type: str
    shift_hours: float
    efficiency: float
    allow_normal: str
    allow_urgent: str
    shift_start: time = time(8, 0, 0)

    def is_priority_allowed(self, priority: Optional[str]) -> bool:
        p = (priority or BatchPriority.NORMAL.value).strip()
        if p == BatchPriority.NORMAL.value:
            return self.allow_normal == YesNo.YES.value
        # urgent / critical 归并到 allow_urgent
        return self.allow_urgent == YesNo.YES.value

    def work_window(self) -> Tuple[datetime, datetime]:
        d = datetime.strptime(self.date_str, "%Y-%m-%d").date()
        start = datetime.combine(d, self.shift_start)
        end = start + timedelta(hours=float(self.shift_hours or 0.0))
        return start, end


class CalendarService:
    """工作日历服务（WorkCalendar）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = CalendarRepository(conn, logger=logger)

    # -------------------------
    # 规范化与校验
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else 0.0
        try:
            return float(value)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)

    @staticmethod
    def _normalize_hhmm(value: Any, field: str, allow_none: bool = True) -> Optional[str]:
        """
        时间标准化为 HH:MM（支持 HH:MM / HH:MM:SS）。
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else "08:00"
        s = str(value).strip().replace("：", ":")
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(s, fmt).time()
                return t.strftime("%H:%M")
            except Exception:
                continue
        raise ValidationError(f"“{field}”格式不合法（期望：HH:MM）", field=field)

    @staticmethod
    def _normalize_date(value: Any) -> str:
        """
        日期标准化为 YYYY-MM-DD。
        - 支持 date/datetime
        - 支持字符串：YYYY-MM-DD / YYYY/MM/DD
        """
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if value is None:
            raise ValidationError("“日期”不能为空", field="日期")
        v = str(value).strip()
        if not v:
            raise ValidationError("“日期”不能为空", field="日期")
        v = v.replace("/", "-")
        try:
            return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
        except Exception:
            raise ValidationError("“日期”格式不合法（期望：YYYY-MM-DD）", field="日期")

    @staticmethod
    def _validate_day_type(value: Any) -> str:
        v = CalendarService._normalize_text(value) or CalendarDayType.WORKDAY.value
        if v not in (CalendarDayType.WORKDAY.value, CalendarDayType.WEEKEND.value, CalendarDayType.HOLIDAY.value):
            raise ValidationError("“类型”不合法（允许：workday / weekend / holiday）", field="类型")
        return v

    @staticmethod
    def _normalize_yesno(value: Any, field: str) -> str:
        v = CalendarService._normalize_text(value) or YesNo.YES.value
        if v in ("是", "y", "Y", "yes", "YES"):
            return YesNo.YES.value
        if v in ("否", "n", "N", "no", "NO"):
            return YesNo.NO.value
        if v not in (YesNo.YES.value, YesNo.NO.value):
            raise ValidationError(f"“{field}”不合法（允许：yes / no）", field=field)
        return v

    # -------------------------
    # CRUD（给页面/Excel用）
    # -------------------------
    def get(self, date_value: Any) -> WorkCalendar:
        d = self._normalize_date(date_value)
        row = self.repo.get(d)
        if row:
            return row
        # 没配则返回默认（不落库）
        return self._default_for_date(d)

    def list_all(self) -> List[WorkCalendar]:
        return self.repo.list_all()

    def list_range(self, start_date: Any, end_date: Any) -> List[WorkCalendar]:
        s = self._normalize_date(start_date)
        e = self._normalize_date(end_date)
        return self.repo.list_range(s, e)

    def upsert(
        self,
        date_value: Any,
        day_type: Any = None,
        shift_hours: Any = None,
        shift_start: Any = None,
        shift_end: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
    ) -> WorkCalendar:
        d = self._normalize_date(date_value)
        dt = self._validate_day_type(day_type)

        sh = self._normalize_float(shift_hours, field="可用工时", allow_none=True)
        eff = self._normalize_float(efficiency, field="效率", allow_none=True)
        if sh is None:
            sh = 8.0 if dt == CalendarDayType.WORKDAY.value else 0.0
        if sh < 0:
            raise ValidationError("“可用工时”不能为负数", field="可用工时")
        if eff is None:
            eff = 1.0
        if eff <= 0:
            raise ValidationError("“效率”必须大于 0", field="效率")

        an = self._normalize_yesno(allow_normal, field="允许普通件")
        au = self._normalize_yesno(allow_urgent, field="允许急件")
        rmk = self._normalize_text(remark)

        ss = self._normalize_hhmm(shift_start, field="班次开始", allow_none=True) or "08:00"
        se = self._normalize_hhmm(shift_end, field="班次结束", allow_none=True)
        # 若给了起止时间，则用其推导可用工时
        if se:
            st_t = datetime.strptime(ss, "%H:%M")
            et_t = datetime.strptime(se, "%H:%M")
            if et_t <= st_t:
                raise ValidationError("“班次结束”必须晚于“班次开始”", field="班次结束")
            sh = (et_t - st_t).total_seconds() / 3600.0
        else:
            # 没填结束时间：根据 shift_hours 推导一个用于展示的 shift_end（不跨天）
            try:
                st_t = datetime.strptime(ss, "%H:%M")
                et_t = st_t + timedelta(hours=float(sh or 0.0))
                if et_t.date() == st_t.date():
                    se = et_t.time().strftime("%H:%M")
            except Exception:
                se = None

        cal = WorkCalendar(
            date=d,
            day_type=dt,
            shift_start=ss,
            shift_end=se,
            shift_hours=float(sh),
            efficiency=float(eff),
            allow_normal=an,
            allow_urgent=au,
            remark=rmk,
        )
        with self.tx_manager.transaction():
            self.upsert_no_tx(cal.to_dict())
        return cal

    def upsert_no_tx(self, calendar_payload: Dict[str, Any]) -> WorkCalendar:
        """
        upsert 工作日历（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        c = calendar_payload if isinstance(calendar_payload, WorkCalendar) else WorkCalendar.from_row(calendar_payload)
        self.repo.upsert(c.to_dict())
        return c

    def delete(self, date_value: Any) -> None:
        d = self._normalize_date(date_value)
        with self.tx_manager.transaction():
            self.repo.delete(d)

    # -------------------------
    # 供算法调用的核心方法（Phase7 会复用）
    # -------------------------
    def _default_for_date(self, date_str: str) -> WorkCalendar:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        # 周末默认不排产（shift_hours=0），工作日默认 8h
        if d.weekday() >= 5:
            return WorkCalendar(
                date=date_str,
                day_type=CalendarDayType.WEEKEND.value,
                shift_hours=0.0,
                efficiency=1.0,
                allow_normal=YesNo.NO.value,
                allow_urgent=YesNo.NO.value,
                remark="默认周末（未配置）",
            )
        return WorkCalendar(
            date=date_str,
            day_type=CalendarDayType.WORKDAY.value,
            shift_hours=8.0,
            efficiency=1.0,
            allow_normal=YesNo.YES.value,
            allow_urgent=YesNo.YES.value,
            remark="默认工作日（未配置）",
        )

    def _policy_for_datetime(self, dt: datetime) -> DayPolicy:
        date_str = dt.date().isoformat()
        row = self.repo.get(date_str)
        cal = row if row else self._default_for_date(date_str)
        # 防御：异常值兜底
        shift_hours = float(cal.shift_hours or 0.0)
        efficiency = float(cal.efficiency or 1.0)
        if efficiency <= 0:
            efficiency = 1.0

        # shift_start/shift_end：默认 08:00；若提供 shift_end 则优先用其推导 shift_hours
        ss = (cal.shift_start or "").strip() if getattr(cal, "shift_start", None) else ""
        if not ss:
            ss = "08:00"
        ss = ss.replace("：", ":")
        try:
            ss_t = datetime.strptime(ss, "%H:%M").time()
        except Exception:
            ss_t = time(8, 0, 0)

        se = (cal.shift_end or "").strip() if getattr(cal, "shift_end", None) else ""
        if se:
            se = se.replace("：", ":")
            try:
                se_t = datetime.strptime(se, "%H:%M").time()
                st_dt = datetime.combine(date.fromisoformat(cal.date), ss_t)
                et_dt = datetime.combine(date.fromisoformat(cal.date), se_t)
                if et_dt > st_dt:
                    shift_hours = (et_dt - st_dt).total_seconds() / 3600.0
            except Exception:
                pass

        return DayPolicy(
            date_str=cal.date,
            day_type=cal.day_type,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=cal.allow_normal,
            allow_urgent=cal.allow_urgent,
            shift_start=ss_t,
        )

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return float(self._policy_for_datetime(dt).efficiency or 1.0)

    def adjust_to_working_time(
        self,
        dt: datetime,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        """
        把任意时间调整到“允许排产的工作时间窗口内”的最早时刻。
        """
        cur = dt
        guard = 0
        while True:
            guard += 1
            if guard > 3660:  # 防御：避免死循环
                raise BusinessError(ErrorCode.CALENDAR_ERROR, "工作日历计算异常：循环次数过多，请检查日历配置。")

            p = self._policy_for_datetime(cur)
            if not p.is_priority_allowed(priority) or p.shift_hours <= 0:
                # 跳到下一天班次开始
                next_day = (cur.date() + timedelta(days=1))
                cur = datetime.combine(next_day, p.shift_start)
                continue

            start, end = p.work_window()
            if cur < start:
                return start
            if cur >= end:
                next_day = (cur.date() + timedelta(days=1))
                cur = datetime.combine(next_day, p.shift_start)
                continue
            return cur

    def add_working_hours(
        self,
        start: datetime,
        hours: float,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        """
        从 start 开始，按“工作时间窗口”累加指定工时，返回结束时间。
        - 会自动跳过非工作日/非工作时段
        - hours 支持小数
        """
        if hours is None:
            raise ValidationError("缺少工时参数", field="hours")
        try:
            total = float(hours)
        except Exception:
            raise ValidationError("工时必须是数字", field="hours")
        if total < 0:
            raise ValidationError("工时不能为负数", field="hours")
        if total == 0:
            return self.adjust_to_working_time(start, priority=priority)

        cur = self.adjust_to_working_time(start, priority=priority)
        remaining = total
        guard = 0

        while remaining > 0:
            guard += 1
            if guard > 36600:
                raise BusinessError(ErrorCode.CALENDAR_ERROR, "工作日历计算异常：循环次数过多，请检查日历配置。")

            p = self._policy_for_datetime(cur)
            if not p.is_priority_allowed(priority) or p.shift_hours <= 0:
                cur = self.adjust_to_working_time(cur, priority=priority)
                continue

            start_w, end_w = p.work_window()
            if cur < start_w:
                cur = start_w
            if cur >= end_w:
                # 下一天
                cur = datetime.combine(cur.date() + timedelta(days=1), p.shift_start)
                cur = self.adjust_to_working_time(cur, priority=priority)
                continue

            available = (end_w - cur).total_seconds() / 3600.0
            if available <= 0:
                cur = datetime.combine(cur.date() + timedelta(days=1), p.shift_start)
                cur = self.adjust_to_working_time(cur, priority=priority)
                continue

            if remaining <= available + 1e-9:
                return cur + timedelta(hours=remaining)

            # 用完当日剩余工时，进入下一天
            remaining -= available
            cur = datetime.combine(cur.date() + timedelta(days=1), p.shift_start)
            cur = self.adjust_to_working_time(cur, priority=priority)

        return cur

    def add_calendar_days(self, start: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        """
        自然日累加（外协周期使用）：不受工作日历影响。
        - days 支持小数
        """
        if days is None:
            raise ValidationError("缺少周期参数", field="days")
        try:
            d = float(days)
        except Exception:
            raise ValidationError("周期必须是数字", field="days")
        if d < 0:
            raise ValidationError("周期不能为负数", field="days")
        return start + timedelta(days=d)

