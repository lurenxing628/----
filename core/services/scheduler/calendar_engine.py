from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from core.algorithm_runtime.calendar_timing_memo import make_lineage_timing_guard, register_calendar_timing_guard
from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models import OperatorCalendar, WorkCalendar
from core.models.enums import BATCH_PRIORITY_VALUES, BatchPriority, CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_hhmm
from core.services.common.normalize import normalize_text
from data.repositories import CalendarRepository, OperatorCalendarRepository

from .calendar_working_hours import Window, WorkingHoursPrefix
from .operator_shift_calendar import OperatorShiftCalendar

# add_calendar_days 的业务量级上界：100 年（365 天 × 100）。
# 依据：外协周期按自然日计，业务上不可能超过百年量级；而 datetime + timedelta 在
# 约 291 万天（datetime.max）处会抛裸 OverflowError，isfinite/非负守卫拦不住有限
# 正巨值（如录入笔误 9999999），故与既有 NaN/Inf/负数守卫对称地补一条量级上界。
MAX_CALENDAR_DAYS = 36500.0
# Engine members whose identity certifies native timing; certificates and the per-decode memo both rely on it.
NATIVE_TIMING_METHODS = ("get_efficiency", "adjust_to_working_time", "add_working_hours", "policy_for_datetime",
                         "_policy_for_datetime", "_policy_for_date", "certified_slot_window", "working_hours_between")
_NORMAL_PRIORITY = BatchPriority.NORMAL.value
_ALLOWED_FLAG = YesNo.YES.value


@lru_cache(maxsize=4096)
def _native_date_isoformat(value: date) -> str:
    return value.isoformat()


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
    _window_start: Optional[datetime] = None
    _window_end: Optional[datetime] = None

    def __post_init__(self) -> None:
        d = datetime.strptime(self.date_str, "%Y-%m-%d").date()
        self._window_start = datetime.combine(d, self.shift_start)
        self._window_end = self._window_start + timedelta(hours=float(self.shift_hours or 0.0))

    def is_priority_allowed(self, priority: Optional[str]) -> bool:
        if priority is None or (type(priority) is str and priority == _NORMAL_PRIORITY):
            return self.allow_normal == _ALLOWED_FLAG
        if type(priority) is str and priority in ("urgent", "critical"):
            return self.allow_urgent == _ALLOWED_FLAG
        # 防御：priority 可能大小写不一致/非字符串/空值
        p = str(priority or _NORMAL_PRIORITY).strip().lower()
        if p not in BATCH_PRIORITY_VALUES:
            p = _NORMAL_PRIORITY
        if p == _NORMAL_PRIORITY:
            return self.allow_normal == _ALLOWED_FLAG
        # urgent / critical 归并到 allow_urgent
        return self.allow_urgent == _ALLOWED_FLAG

    def work_window(self) -> Tuple[datetime, datetime]:
        start = self._window_start
        end = self._window_end
        if start is None or end is None:
            d = datetime.strptime(self.date_str, "%Y-%m-%d").date()
            start = datetime.combine(d, self.shift_start)
            end = start + timedelta(hours=float(self.shift_hours or 0.0))
            self._window_start = start
            self._window_end = end
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
        self.operator_shift_calendar = OperatorShiftCalendar(conn, logger=logger)
        # 每次排产会对同一日期重复查询多次；按 (operator_id, date_str) 做轻量缓存可显著减少 DB 访问
        self._policy_cache: Dict[Tuple[str, str], DayPolicy] = {}
        # 工作小时差按 (operator_id, 优先级类别) 维护逐日窗口前缀，与策略缓存同生命周期。
        self._working_hours_prefix: Dict[Tuple[str, str], WorkingHoursPrefix] = {}

    def clear_policy_cache(self) -> None:
        """
        清空 DayPolicy 缓存。

        说明：缓存用于排产过程加速，但当 WorkCalendar/OperatorCalendar 被修改后，
        必须清空缓存以保证“立即生效”（回归用例依赖该语义）。
        """
        self._policy_cache.clear()
        self._working_hours_prefix.clear()

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        # Only native strings bypass the general NaN/custom-object checks.
        if type(value) is str:
            return value.strip() or None
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

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> Any:
        if op_id:
            row_op = self.operator_calendar_repo.get(op_id, date_str)
            if row_op:
                return row_op
        row = self.repo.get(date_str)
        return row if row else self._default_for_date(date_str)

    @staticmethod
    def _normalize_efficiency(cal: Any) -> float:
        raw_efficiency = getattr(cal, "efficiency", 1.0)
        if raw_efficiency is None or (isinstance(raw_efficiency, str) and raw_efficiency.strip() == ""):
            raw_efficiency = 1.0
        if isinstance(raw_efficiency, bool):
            raise ValidationError("日历效率必须是数字", field="efficiency")
        try:
            efficiency = float(raw_efficiency)
        except Exception:
            raise ValidationError("日历效率必须是数字", field="efficiency") from None
        if not math.isfinite(efficiency):
            raise ValidationError("日历效率必须是有限数字", field="efficiency")
        if efficiency <= 0:
            raise ValidationError("日历效率必须大于 0", field="efficiency")
        return efficiency

    @staticmethod
    def _parse_shift_start(cal: Any) -> time:
        ss = normalize_hhmm(getattr(cal, "shift_start", None), field="班次开始", allow_none=True) or "08:00"
        return datetime.strptime(ss, "%H:%M").time()

    @staticmethod
    def _override_shift_hours_by_shift_end(cal: Any, *, date_str: str, shift_start_t: time, shift_hours: float) -> float:
        se = normalize_hhmm(getattr(cal, "shift_end", None), field="班次结束", allow_none=True)
        if not se:
            return shift_hours
        se_t = datetime.strptime(se, "%H:%M").time()
        base_d = date.fromisoformat(getattr(cal, "date", None) or date_str)
        st_dt = datetime.combine(base_d, shift_start_t)
        et_dt = datetime.combine(base_d, se_t)
        # 跨午夜：shift_end <= shift_start 表示次日结束（含相等：24h）
        if et_dt <= st_dt:
            et_dt = et_dt + timedelta(days=1)
        return (et_dt - st_dt).total_seconds() / 3600.0

    def _policy_for_date(self, date_str: str, operator_id: Optional[str] = None) -> DayPolicy:
        """获取某个“日期键”的 DayPolicy（不做跨午夜归属判断）。"""
        op_id = self._normalize_text(operator_id) if operator_id is not None else None
        cache_key = ((op_id or ""), date_str)
        cached = self._policy_cache.get(cache_key)
        if cached is not None:
            return cached

        cal = self._resolve_calendar_row(date_str, op_id)

        raw_shift_hours = getattr(cal, "shift_hours", 0.0)
        if raw_shift_hours is None or (isinstance(raw_shift_hours, str) and raw_shift_hours.strip() == ""):
            raw_shift_hours = 0.0
        if isinstance(raw_shift_hours, bool):
            raise ValidationError("班次工时必须是数字", field="shift_hours")
        try:
            shift_hours = float(raw_shift_hours)
        except Exception:
            raise ValidationError("班次工时必须是数字", field="shift_hours") from None
        if not math.isfinite(shift_hours):
            raise ValidationError("班次工时必须是有限数字", field="shift_hours")
        if shift_hours < 0:
            raise ValidationError("班次工时不能为负数", field="shift_hours")
        efficiency = self._normalize_efficiency(cal)

        # shift_start/shift_end：默认 08:00；若提供 shift_end 则优先用其推导 shift_hours
        ss_t = self._parse_shift_start(cal)
        shift_hours = self._override_shift_hours_by_shift_end(cal, date_str=date_str, shift_start_t=ss_t, shift_hours=shift_hours)

        p = DayPolicy(
            date_str=getattr(cal, "date", None) or date_str,
            day_type=cal.day_type,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=cal.allow_normal,
            allow_urgent=cal.allow_urgent,
            shift_start=ss_t,
        )
        if op_id and not isinstance(cal, OperatorCalendar):
            p = self.operator_shift_calendar.apply_policy(p, op_id)
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
        today = dt.date()
        today_str = _native_date_isoformat(today) if type(today) is date else today.isoformat()
        p_today = self._policy_for_date(today_str, operator_id=operator_id)
        start_today, end_today = p_today.work_window()
        if start_today <= dt < end_today:
            return p_today

        # Today's empty/rest window may start at 00:00 while yesterday's night shift is still running.
        if dt.date() > date.min:
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
        if isinstance(hours, bool):
            raise ValidationError("工时必须是数字", field="hours")
        try:
            total = float(hours)
        except Exception:
            raise ValidationError("工时必须是数字", field="hours") from None
        if not math.isfinite(total):
            raise ValidationError("工时必须是有限数字", field="hours")
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

    @staticmethod
    def _priority_class(priority: Optional[str]) -> str:
        # Mirrors DayPolicy.is_priority_allowed: urgent and critical share the urgent flag, everything else is normal.
        text = str(priority or _NORMAL_PRIORITY).strip().lower()
        return "urgent" if text in ("urgent", "critical") else _NORMAL_PRIORITY

    def _allowed_window(self, day: date, *, priority: Optional[str], operator_id: Optional[str]) -> Window:
        policy = self._policy_for_date(day.isoformat(), operator_id=operator_id)
        if not policy.is_priority_allowed(priority) or policy.shift_hours <= 0:
            return None
        return policy.work_window()

    def working_hours_between(
        self,
        start: datetime,
        end: datetime,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> float:
        """
        start 到 end 之间允许该优先级排产的工作小时数（end 早于 start 时为负）。

        与 add_working_hours 同一套 DayPolicy 口径：不可排产日、不允许该优先级的日子贡献 0；
        跨午夜班次按“班次开始日”归属，最多延伸到次日。
        """
        op_id = self._normalize_text(operator_id) if operator_id is not None else None
        key = ((op_id or ""), self._priority_class(priority))
        prefix = self._working_hours_prefix.get(key)
        if prefix is None:
            prefix = WorkingHoursPrefix(lambda day: self._allowed_window(day, priority=priority, operator_id=op_id))
            self._working_hours_prefix[key] = prefix
        return prefix.between(start, end)

    def add_calendar_days(self, start: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        """
        自然日累加（外协周期使用）：不受工作日历影响。
        - days 支持小数
        """
        if days is None:
            raise ValidationError("缺少周期参数", field="days")
        if isinstance(days, bool):
            raise ValidationError("周期必须是数字", field="days")
        try:
            d = float(days)
        except Exception:
            raise ValidationError("周期必须是数字", field="days") from None
        if not math.isfinite(d):
            raise ValidationError("周期必须是有限数字", field="days")
        if d < 0:
            raise ValidationError("周期不能为负数", field="days")
        if d > MAX_CALENDAR_DAYS:
            raise ValidationError(
                f"外协周期天数超出合理范围（不能超过 {int(MAX_CALENDAR_DAYS)} 天）",
                field="days",
            )
        return start + timedelta(days=d)


# Subclasses that only change how calendar rows are resolved keep the engine's pure timing surface.
register_calendar_timing_guard(CalendarEngine, make_lineage_timing_guard(CalendarEngine, NATIVE_TIMING_METHODS))
