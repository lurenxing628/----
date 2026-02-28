from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models import WorkCalendar
from core.models.enums import BatchPriority, CalendarDayType, YesNo
from core.services.common.normalize import normalize_text
from data.repositories import CalendarRepository, OperatorCalendarRepository


@dataclass
class DayPolicy:
    """
    某天的排产策略（从 WorkCalendar/OperatorCalendar 推导）。

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
        # 防御：priority 可能大小写不一致/非字符串/空值
        p = str(priority or BatchPriority.NORMAL.value).strip().lower()
        if p not in (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value):
            p = BatchPriority.NORMAL.value
        if p == BatchPriority.NORMAL.value:
            return self.allow_normal == YesNo.YES.value
        # urgent / critical 归并到 allow_urgent
        return self.allow_urgent == YesNo.YES.value

    def work_window(self) -> Tuple[datetime, datetime]:
        d = datetime.strptime(self.date_str, "%Y-%m-%d").date()
        start = datetime.combine(d, self.shift_start)
        end = start + timedelta(hours=float(self.shift_hours or 0.0))
        return start, end


class CalendarEngine:
    """
    工作日历“引擎侧”能力（给排产算法使用）。

    说明：
    - 负责 DayPolicy 推导与时间推进（adjust/add/efficiency）
    - 读取日历数据（WorkCalendar/OperatorCalendar）但不负责 CRUD/导入
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = CalendarRepository(conn, logger=logger)
        self.operator_calendar_repo = OperatorCalendarRepository(conn, logger=logger)
        # 每次排产会对同一日期重复查询多次；按 (operator_id, date_str) 做轻量缓存可显著减少 DB 访问
        self._policy_cache: Dict[Tuple[str, str], DayPolicy] = {}

    def clear_policy_cache(self) -> None:
        """
        清空 DayPolicy 缓存。

        说明：缓存用于排产过程加速，但当 WorkCalendar/OperatorCalendar 被修改后，
        必须清空缓存以保证“立即生效”（回归用例依赖该语义）。
        """
        self._policy_cache.clear()

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

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

    def _policy_for_date(self, date_str: str, operator_id: Optional[str] = None) -> DayPolicy:
        """获取某个“日期键”的 DayPolicy（不做跨午夜归属判断）。"""
        op_id = self._normalize_text(operator_id) if operator_id is not None else None
        cache_key = ((op_id or ""), date_str)
        cached = self._policy_cache.get(cache_key)
        if cached is not None:
            return cached

        cal: Any = None
        if op_id:
            row_op = self.operator_calendar_repo.get(op_id, date_str)
            if row_op:
                cal = row_op
        if cal is None:
            row = self.repo.get(date_str)
            cal = row if row else self._default_for_date(date_str)

        # 防御：异常值兜底
        shift_hours = float(getattr(cal, "shift_hours", 0.0) or 0.0)
        efficiency = float(getattr(cal, "efficiency", 1.0) or 1.0)
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
                base_d = date.fromisoformat(getattr(cal, "date", None) or date_str)
                st_dt = datetime.combine(base_d, ss_t)
                et_dt = datetime.combine(base_d, se_t)
                # 跨午夜：shift_end <= shift_start 表示次日结束（含相等：24h）
                if et_dt <= st_dt:
                    et_dt = et_dt + timedelta(days=1)
                shift_hours = (et_dt - st_dt).total_seconds() / 3600.0
            except (ValueError, TypeError):
                # shift_end 非法：回退到 shift_hours（已从 cal.shift_hours 读取）
                pass

        p = DayPolicy(
            date_str=getattr(cal, "date", None) or date_str,
            day_type=cal.day_type,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=cal.allow_normal,
            allow_urgent=cal.allow_urgent,
            shift_start=ss_t,
        )
        self._policy_cache[cache_key] = p
        return p

    def _policy_for_datetime(self, dt: datetime, operator_id: Optional[str] = None) -> DayPolicy:
        """
        获取某时刻所属的 DayPolicy（支持跨午夜班次）。

        关键约定：
        - WorkCalendar/OperatorCalendar 以“shift_start 所在日期”为键；
        - 当某日班次跨到次日（shift_end <= shift_start / shift_hours 跨日）时，
          次日凌晨的时间点应归属到“前一天”的工作窗内。
        """
        today_str = dt.date().isoformat()
        p_today = self._policy_for_date(today_str, operator_id=operator_id)
        start_today, end_today = p_today.work_window()
        if start_today <= dt < end_today:
            return p_today

        # 跨午夜：凌晨可能仍属于前一天的工作窗
        if dt < start_today:
            prev_str = (dt.date() + timedelta(days=-1)).isoformat()
            p_prev = self._policy_for_date(prev_str, operator_id=operator_id)
            start_prev, end_prev = p_prev.work_window()
            if start_prev <= dt < end_prev:
                return p_prev

        return p_today

    def policy_for_datetime(self, dt: datetime, operator_id: Optional[str] = None) -> DayPolicy:
        """
        公共接口：获取某时刻所在日期的排产策略（DayPolicy）。
        """
        return self._policy_for_datetime(dt, operator_id=operator_id)

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return float(self._policy_for_datetime(dt, operator_id=operator_id).efficiency or 1.0)

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

            p = self._policy_for_datetime(cur, operator_id=operator_id)
            if not p.is_priority_allowed(priority) or p.shift_hours <= 0:
                # 跳到下一天：使用 00:00 触发“下一天 policy”，避免沿用当天 shift_start
                next_day = cur.date() + timedelta(days=1)
                cur = datetime.combine(next_day, time(0, 0, 0))
                continue

            start, end = p.work_window()
            if cur < start:
                return start
            if cur >= end:
                next_day = cur.date() + timedelta(days=1)
                cur = datetime.combine(next_day, time(0, 0, 0))
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
            raise ValidationError("工时必须是数字", field="hours") from None
        if total < 0:
            raise ValidationError("工时不能为负数", field="hours")
        if total == 0:
            return self.adjust_to_working_time(start, priority=priority, operator_id=operator_id)

        cur = self.adjust_to_working_time(start, priority=priority, operator_id=operator_id)
        remaining = total
        guard = 0

        while remaining > 0:
            guard += 1
            if guard > 36600:
                raise BusinessError(ErrorCode.CALENDAR_ERROR, "工作日历计算异常：循环次数过多，请检查日历配置。")

            p = self._policy_for_datetime(cur, operator_id=operator_id)
            if not p.is_priority_allowed(priority) or p.shift_hours <= 0:
                cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_id)
                continue

            start_w, end_w = p.work_window()
            if cur < start_w:
                cur = start_w
            if cur >= end_w:
                # 下一天
                cur = datetime.combine(cur.date() + timedelta(days=1), time(0, 0, 0))
                cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_id)
                continue

            available = (end_w - cur).total_seconds() / 3600.0
            if available <= 0:
                # 防御：避免跨午夜班次下回退到 00:00 造成重复计时
                cur = end_w
                cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_id)
                continue

            if remaining <= available + 1e-9:
                return cur + timedelta(hours=remaining)

            # 用完当前工作窗剩余工时：推进到该窗结束，再跳到下一可排产时刻
            remaining -= available
            cur = end_w
            cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_id)

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
            raise ValidationError("周期必须是数字", field="days") from None
        if d < 0:
            raise ValidationError("周期不能为负数", field="days")
        return start + timedelta(days=d)

