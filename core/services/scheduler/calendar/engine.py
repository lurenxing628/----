from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from core.algorithm_runtime.calendar_timing_memo import make_lineage_timing_guard, register_calendar_timing_guard
from core.errors import BusinessError, ErrorCode, ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import (
    decode_periods,
    encode_periods,
)
from core.models.enums import BATCH_PRIORITY_VALUES, BatchPriority, CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_hhmm
from core.services.common.normalize import normalize_text
from data.repositories import CalendarRepository, OperatorCalendarRepository

from .defaults import read_default_periods
from .operator_shift import OperatorShiftCalendar
from .period_offsets import offset_hours, period_offsets
from .working_hours import WorkingHoursPrefix

# add_calendar_days 的业务量级上界：100 年（365 天 × 100）。
# 依据：外协周期按自然日计，业务上不可能超过百年量级；而 datetime + timedelta 在
# 约 291 万天（datetime.max）处会抛裸 OverflowError，isfinite/非负守卫拦不住有限
# 正巨值（如录入笔误 9999999），故与既有 NaN/Inf/负数守卫对称地补一条量级上界。
MAX_CALENDAR_DAYS = 36500.0
# Engine members whose identity certifies native timing; certificates and the per-decode memo both rely on it.
NATIVE_TIMING_METHODS = ("get_efficiency", "adjust_to_working_time", "add_working_hours", "add_effective_hours", "_add_hours", "policy_for_datetime",
                         "_policy_for_date", "_effective_segments", "_allowed_segments",
                         "certified_slot_window", "working_hours_between", "default_periods")
_NORMAL_PRIORITY = BatchPriority.NORMAL.value
_ALLOWED_FLAG = YesNo.YES.value


def _parse_finite_float_value(raw: Any, *, field: str, number_msg: str, finite_msg: str) -> float:
    if isinstance(raw, bool):
        raise ValidationError(number_msg, field=field)
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError(number_msg, field=field) from None
    if not math.isfinite(value):
        raise ValidationError(finite_msg, field=field)
    return value


@lru_cache(maxsize=4096)
def _native_date_isoformat(value: date) -> str:
    return value.isoformat()


@lru_cache(maxsize=4096)
def _dated_period_windows(date_str, offsets, hours):
    base = datetime.combine(date.fromisoformat(date_str), time.min)
    remaining, result = hours, []
    for low, high in offsets:
        if remaining <= 0:
            break
        start, end = base + timedelta(minutes=low), base + timedelta(minutes=high)
        end = min(end, start + timedelta(hours=remaining))
        result.append((start, end))
        remaining -= (end - start).total_seconds() / 3600
    return tuple(result)


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
    _window_start: datetime = field(init=False, repr=False)
    _window_end: datetime = field(init=False, repr=False)
    periods_json: Optional[str] = None
    _period_offsets: Optional[tuple] = None

    def __post_init__(self) -> None:
        if self.periods_json is not None:
            if self._period_offsets is None:
                self._period_offsets = period_offsets(decode_periods(self.periods_json))
            windows = self.work_windows()
            if windows:
                self._window_start, self._window_end = windows[0][0], windows[-1][1]
            else:
                d = date.fromisoformat(self.date_str)
                self._window_start = self._window_end = datetime.combine(d, self.shift_start)
        else:
            d = date.fromisoformat(self.date_str)
            self._window_start = datetime.combine(d, self.shift_start)
            self._window_end = self._window_start + timedelta(hours=self.shift_hours)

    def work_windows(self) -> tuple:
        if self.periods_json is not None:
            return _dated_period_windows(self.date_str, self._period_offsets, self.shift_hours)
        start, end = self.work_window()
        return ((start, end),) if start < end else ()

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
        return self._window_start, self._window_end

    def is_working(self) -> bool:
        return self.shift_hours > 0 and (self.is_priority_allowed(_NORMAL_PRIORITY) or self.is_priority_allowed("urgent"))


class CalendarEngine:
    """
    工作日历“引擎侧”能力（给排产算法使用）。

    说明：
    - 负责 DayPolicy 推导与时间推进（adjust/add/efficiency）
    - 读取日历数据（WorkCalendar/OperatorCalendar）但不负责 CRUD/导入
    """

    def __init__(self, conn, logger=None, *, capture=None, shift_repo=None):
        self.conn = conn
        self.logger = logger
        self.capture = capture
        self.repo = CalendarRepository(conn, logger=logger)
        self.operator_calendar_repo = OperatorCalendarRepository(conn, logger=logger)
        self.operator_shift_calendar = OperatorShiftCalendar(conn, logger=logger, capture=capture, repo=shift_repo)
        self._captured_global_rows = (None if capture is None else {
            str(row["date"]): row for row in capture.business_table("WorkCalendar")})
        self._captured_personal_rows = (None if capture is None else {
            (row["operator_id"], str(row["date"])): row for row in capture.business_table("OperatorCalendar")})
        # 本引擎拥有一次请求/排产快照的日期与班次事实；维护入口统一清空派生缓存。
        self._default_periods_json: Optional[str] = None
        self._default_periods = None
        self._default_period_hours = 0.0
        self._period_facts: Dict[str, tuple] = {}
        self._public_calendar_rows: Dict[str, Any] = {}
        self._operator_calendar_rows: Dict[str, Dict[str, Any]] = {}
        self._public_policy_cache: Dict[str, DayPolicy] = {}
        self._policy_cache: Dict[Tuple[str, str], DayPolicy] = {}
        self._policy_operator_keys: Dict[str, Dict[Tuple[str, str], None]] = {}
        self._segment_cache: Dict[str, Dict[date, tuple]] = {}
        # 工作小时差按 (operator_id, 优先级类别) 维护逐日窗口前缀，与策略缓存同生命周期。
        self._working_hours_prefix: Dict[Tuple[str, str], WorkingHoursPrefix] = {}

    def clear_policy_cache(self) -> None:
        """
        清空 DayPolicy 缓存。

        说明：缓存用于排产过程加速，但当 WorkCalendar/OperatorCalendar 被修改后，
        必须清空缓存以保证“立即生效”（回归用例依赖该语义）。
        """
        self._default_periods_json = None
        self._default_periods = None
        self._default_period_hours = 0.0
        self._period_facts.clear()
        self._public_calendar_rows.clear()
        self._operator_calendar_rows.clear()
        self._public_policy_cache.clear()
        self._policy_cache.clear()
        self._policy_operator_keys.clear()
        self._segment_cache.clear()
        self._working_hours_prefix.clear()
        self.operator_shift_calendar.clear_cache()

    def discard_operator_policy(self, operator_id: str) -> None:
        """Release one streamed person's policies; shared calendar/shift facts remain."""
        op_id = self._normalize_text(operator_id)
        if not op_id:
            return
        for key in self._policy_operator_keys.pop(op_id, ()):
            self._policy_cache.pop(key, None)
        self._operator_calendar_rows.pop(op_id, None)
        self._segment_cache.pop(op_id, None)
        for priority in (_NORMAL_PRIORITY, "urgent"):
            self._working_hours_prefix.pop((op_id, priority), None)
        self.operator_shift_calendar.discard_operator(op_id)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        # Only native strings bypass the general NaN/custom-object checks.
        if type(value) is str:
            return value if value.strip() else None
        return normalize_text(value)

    def default_periods(self):
        """The engine owns these parsed defaults; callers consume them read-only."""
        if self._default_periods is None:
            periods = (read_default_periods(self.conn, capture=self.capture) if self._default_periods_json is None
                       else decode_periods(self._default_periods_json))
            if not periods:
                raise ValidationError("默认工作时间至少需要一个工作时段。", field="periods")
            self._default_periods = periods
            if self._default_periods_json is None:
                self._default_periods_json = encode_periods(periods)
            _, self._default_period_hours = self._period_facts_for_json(self._default_periods_json, periods)
        return self._default_periods

    def _period_facts_for_json(self, periods_json, periods=None):
        if periods_json not in self._period_facts:
            offsets = period_offsets(decode_periods(periods_json) if periods is None else periods)
            self._period_facts[periods_json] = offsets, offset_hours(offsets)
        return self._period_facts[periods_json]

    def _default_for_date(self, date_str: str) -> WorkCalendar:
        if date_str in self._public_calendar_rows:
            return self._public_calendar_rows[date_str]
        d = date.fromisoformat(date_str)
        # 周末默认不排产；工作日按上午和下午两段，午休不计工时。
        if d.weekday() >= 5:
            row = WorkCalendar(
                date=date_str,
                day_type=CalendarDayType.WEEKEND.value,
                shift_hours=0.0,
                efficiency=1.0,
                allow_normal=YesNo.NO.value,
                allow_urgent=YesNo.NO.value,
                remark="默认周末（未配置）",
            )
        else:
            periods = self.default_periods()
            row = WorkCalendar(
                date=date_str,
                day_type=CalendarDayType.WORKDAY.value,
                shift_start=periods[0]["start"], shift_end=periods[-1]["end"],
                shift_hours=self._default_period_hours,
                periods_json=self._default_periods_json,
                efficiency=1.0,
                allow_normal=YesNo.YES.value,
                allow_urgent=YesNo.YES.value,
                remark="默认工作日（未配置）",
            )
        self._public_calendar_rows[date_str] = row
        return row

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> Any:
        if op_id:
            rows = self._operator_calendar_rows.setdefault(op_id, {})
            if date_str not in rows:
                if self._captured_personal_rows is None:
                    rows[date_str] = self.operator_calendar_repo.get(op_id, date_str)
                else:
                    raw = self._captured_personal_rows.get((op_id, date_str))
                    rows[date_str] = OperatorCalendar.from_row(raw) if raw is not None else None
            row_op = rows[date_str]
            if row_op:
                return row_op
        if date_str not in self._public_calendar_rows:
            if self._captured_global_rows is None:
                row = self.repo.get(date_str)
            else:
                raw = self._captured_global_rows.get(date_str)
                row = WorkCalendar.from_row(raw) if raw is not None else None
            self._public_calendar_rows[date_str] = row if row else self._default_for_date(date_str)
        return self._public_calendar_rows[date_str]

    @staticmethod
    def _parse_shift_start(cal: Any) -> time:
        ss = normalize_hhmm(cal.shift_start, field="班次开始") or "08:00"
        return datetime.strptime(ss, "%H:%M").time()

    @staticmethod
    def _override_shift_hours_by_shift_end(cal: Any, *, date_str: str, shift_start_t: time, shift_hours: float) -> float:
        se = normalize_hhmm(cal.shift_end, field="班次结束")
        if not se:
            return shift_hours
        se_t = datetime.strptime(se, "%H:%M").time()
        base_d = date.fromisoformat(cal.date or date_str)
        st_dt = datetime.combine(base_d, shift_start_t)
        et_dt = datetime.combine(base_d, se_t)
        # 跨午夜：shift_end <= shift_start 表示次日结束（含相等：24h）
        if et_dt <= st_dt:
            et_dt = et_dt + timedelta(days=1)
        return (et_dt - st_dt).total_seconds() / 3600.0

    def _policy_for_date(self, date_str: str, operator_id: Optional[str] = None) -> DayPolicy:
        """获取某个“日期键”的 DayPolicy（不做跨午夜归属判断）。"""
        op_id = self._normalize_text(operator_id) if operator_id is not None else None
        if op_id is not None:
            cache_key = (op_id, date_str)
            cached = self._policy_cache.get(cache_key)
            if cached is not None:
                return cached
        elif date_str in self._public_policy_cache:
            return self._public_policy_cache[date_str]

        # Resolve personal facts first: an explicit personal day never consumes global data.
        cal = self._resolve_calendar_row(date_str, op_id)
        if isinstance(cal, OperatorCalendar):
            p = self._policy_from_calendar(date_str, cal)
        else:
            p = self._public_policy_cache.get(date_str)
            if p is None:
                p = self._policy_from_calendar(date_str, cal)
                self._public_policy_cache[date_str] = p
            if op_id is not None:
                p = self.operator_shift_calendar.apply_policy(p, op_id, prepare_periods=self._period_facts_for_json)
        if op_id is not None:
            self._policy_cache[(op_id, date_str)] = p
            self._policy_operator_keys.setdefault(op_id, {})[(op_id, date_str)] = None
        return p

    def _policy_from_calendar(self, date_str: str, cal: Any) -> DayPolicy:
        """Normalize a public date once, or one explicit personal override."""
        shift_hours = float(cal.shift_hours)
        efficiency = float(cal.efficiency)

        # shift_start/shift_end：默认 08:00；若提供 shift_end 则优先用其推导 shift_hours
        ss_t = self._parse_shift_start(cal)
        periods_json = cal.periods_json
        offsets = None
        if periods_json is not None:
            offsets, shift_hours = self._period_facts_for_json(periods_json)
        else:
            shift_hours = self._override_shift_hours_by_shift_end(
                cal, date_str=date_str, shift_start_t=ss_t, shift_hours=shift_hours,
            )

        p = DayPolicy(
            date_str=cal.date or date_str,
            day_type=cal.day_type,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=cal.allow_normal,
            allow_urgent=cal.allow_urgent,
            shift_start=ss_t,
            periods_json=periods_json,
            _period_offsets=offsets,
        )
        return p

    def policy_for_datetime(self, dt: datetime, operator_id: Optional[str] = None) -> DayPolicy:
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
        if any(start <= dt < end for start, end in p_today.work_windows()):
            return p_today

        # Today's empty/rest window may start at 00:00 while yesterday's night shift is still running.
        if today > date.min:
            prev_str = (today + timedelta(days=-1)).isoformat()
            p_prev = self._policy_for_date(prev_str, operator_id=operator_id)
            if any(start <= dt < end for start, end in p_prev.work_windows()):
                return p_prev

        return p_today

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return self.policy_for_datetime(dt, operator_id=operator_id).efficiency

    def capacity_hours_between(self, start: datetime, end: datetime, *, priority=None, operator_id=None) -> float:
        """Efficiency-weighted capacity over the same disjoint pieces used by scheduling."""
        day, total = start.date(), 0.0
        if (end.date() - day).days > 4000:
            raise ValidationError("产能计算日期范围过长。", field="calendar")
        while day <= end.date() and start < end:
            for low, high, policy in self._effective_segments(day, operator_id):
                low, high = max(start, low), min(end, high)
                if low < high and policy.is_priority_allowed(priority):
                    total += (high - low).total_seconds() / 3600 * policy.efficiency
            if day == date.max:
                break
            day += timedelta(days=1)
        return total

    def _effective_segments(self, day: date, operator_id: Optional[str] = None) -> tuple:
        """Disjoint natural-day pieces; today's window overrides yesterday's tail."""
        op_id = self._normalize_text(operator_id) if operator_id is not None else None
        cache = self._segment_cache.setdefault(op_id or "", {})
        if day in cache:
            return cache[day]
        lo = datetime.combine(day, time.min)
        hi = datetime.max if day == date.max else lo + timedelta(days=1)
        policies = [self._policy_for_date(day.isoformat(), operator_id=op_id)]
        if day > date.min:
            policies.append(self._policy_for_date((day - timedelta(days=1)).isoformat(), operator_id=op_id))
        windows = [(p, max(lo, start), min(hi, end)) for p in policies for start, end in p.work_windows()]
        windows = [(p, start, end) for p, start, end in windows if start < end]
        edges = sorted({point for _, start, end in windows for point in (start, end)})
        segments = []
        for start, end in zip(edges, edges[1:]):
            owner = next((p for p, left, right in windows if left <= start < right), None)
            if owner is not None:
                segments.append((start, end, owner))
        result = tuple(segments)
        cache[day] = result
        return result

    def adjust_to_working_time(
        self, dt: datetime, priority: Optional[str] = None,
        machine_id: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> datetime:
        """Advance to the earliest allowed segment, including today's later shift."""
        cur = dt
        for _ in range(3660):
            for start, end in self._allowed_segments(cur.date(), priority=priority, operator_id=operator_id):
                if cur < end:
                    return max(cur, start)
            if cur.date() == date.max:
                raise BusinessError(ErrorCode.CALENDAR_ERROR, "已到可表示日期上限，没有后续可排产时间。")
            cur = datetime.combine(cur.date() + timedelta(days=1), time.min)
        raise BusinessError(ErrorCode.CALENDAR_ERROR, "工作日历计算异常：循环次数过多，请检查日历配置。")

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
        return self._add_hours(start, hours, priority, operator_id, efficiency_weighted=False)

    def add_effective_hours(
        self,
        start: datetime,
        hours: float,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        """消耗有效加工工时；每个实际工作班段按其自己的效率折算。"""
        return self._add_hours(start, hours, priority, operator_id, efficiency_weighted=True)

    def _add_hours(self, start, hours, priority, operator_id, *, efficiency_weighted):
        if hours is None:
            raise ValidationError("缺少工时参数", field="hours")
        total = _parse_finite_float_value(
            hours, field="hours", number_msg="工时必须是数字", finite_msg="工时必须是有限数字",
        )
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

            end_w, policy = next((end, policy) for left, end, policy in self._effective_segments(
                cur.date(), operator_id) if left <= cur < end and policy.is_priority_allowed(priority))
            efficiency = policy.efficiency if efficiency_weighted else 1.0
            available = (end_w - cur).total_seconds() / 3600.0
            capacity = available * efficiency
            if remaining <= capacity + 1e-9:
                return cur + timedelta(hours=min(remaining / efficiency, available))

            # 用完当前工作窗剩余工时：推进到该窗结束，再跳到下一可排产时刻
            remaining -= capacity
            cur = end_w
            cur = self.adjust_to_working_time(cur, priority=priority, operator_id=operator_id)

        return cur

    @staticmethod
    def _priority_class(priority: Optional[str]) -> str:
        # Mirrors DayPolicy.is_priority_allowed: urgent and critical share the urgent flag, everything else is normal.
        text = str(priority or _NORMAL_PRIORITY).strip().lower()
        return "urgent" if text in ("urgent", "critical") else _NORMAL_PRIORITY

    def _allowed_segments(self, day: date, *, priority: Optional[str], operator_id: Optional[str]) -> tuple:
        return tuple((start, end) for start, end, policy in self._effective_segments(day, operator_id)
                     if policy.is_priority_allowed(priority))

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
            prefix = WorkingHoursPrefix(lambda day: self._allowed_segments(day, priority=priority, operator_id=op_id))
            self._working_hours_prefix[key] = prefix
        return prefix.between(start, end)

    def add_calendar_days(self, start: datetime, days: Optional[float], machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        """
        自然日累加（外协周期使用）：不受工作日历影响。
        - days 支持小数
        - 采用复核、排产检查按工序原值传周期，未单独设置周期的外协工序会传 None，这里按缺少周期拒绝。
        """
        if days is None:
            raise ValidationError("缺少周期参数", field="days")
        d = _parse_finite_float_value(
            days, field="days", number_msg="周期必须是数字", finite_msg="周期必须是有限数字",
        )
        if d < 0:
            raise ValidationError("周期不能为负数", field="days")
        if d > MAX_CALENDAR_DAYS:
            raise ValidationError(
                f"外协周期天数超出合理范围（不能超过 {int(MAX_CALENDAR_DAYS)} 天）",
                field="days",
            )
        return start + timedelta(days=d)


# Subclasses that only change how calendar rows are resolved keep the engine's pure timing surface.
register_calendar_timing_guard(CalendarEngine, make_lineage_timing_guard(CalendarEngine, NATIVE_TIMING_METHODS),
                               calendar_days_guard=make_lineage_timing_guard(CalendarEngine, ("add_calendar_days",)))
