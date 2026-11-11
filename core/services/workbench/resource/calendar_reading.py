"""Engine reading of stored or proposed global calendar rows, without SQL writes.

Month totals count overnight tails once.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.services.scheduler.calendar.engine import CalendarEngine

from .calendar_summary import owned_hours

CalendarRow = Union[WorkCalendar, OperatorCalendar, Dict[str, Any]]


class CalendarProjection(CalendarEngine):
    """Overlay raw/proposed global rows (keyed by date) on an existing engine, without SQL writes.

    默认工作时段、它的规范化文本和已解析的时段事实都直接用来源引擎的，不在这里再规范化或编码一遍。
    """

    def __init__(self, rows: Mapping[str, CalendarRow], *, engine: CalendarEngine):
        self._source = engine
        self._inputs = engine._inputs
        self.operator_shift_calendar = engine.operator_shift_calendar
        self.shift_profiles = engine.shift_profiles
        self.personal_rows = engine.personal_rows
        self._default_rows = engine._default_rows
        self._default_facts = engine._default_facts
        self._period_facts = engine._period_facts
        self._decoded_periods = engine._decoded_periods
        self.global_rows: Mapping[str, Any] = rows
        self._public_calendar_rows = {}
        self._operator_calendar_rows = {}
        self._public_policy_cache = {}
        self._policy_cache = {}
        self._policy_operator_keys = {}
        self._segment_cache = {}
        self._working_hours_prefix = {}
        self._decode_checkpoint_signature = None

    def default_period_facts(self) -> Tuple[List[Dict[str, Any]], str]:
        if self._default_facts is None:
            self._default_facts = self._source.default_period_facts()
        return self._default_facts

    def with_rows(self, rows: Mapping[str, CalendarRow]) -> CalendarProjection:
        return CalendarProjection(rows, engine=self._source)

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> Union[WorkCalendar, OperatorCalendar]:
        # 用到哪天才解析哪天：月合计多读的次月 1 日即使存坏了，也只让合计未知，不牵连本月。
        row = self.global_rows.get(date_str)
        return (
            (row if isinstance(row, (WorkCalendar, OperatorCalendar)) else WorkCalendar.from_row(row))
            if row is not None
            else self._default_for_date(date_str)
        )


def effective_calendar_day(day: str, row: Optional[CalendarRow], *, projection: CalendarProjection) -> Dict[str, Any]:
    # Date-key policy is deliberate: midnight may still belong to yesterday's shift.
    try:
        if (row is None and day not in projection.global_rows) or (
            day in projection.global_rows and projection.global_rows[day] is row
        ):
            engine = projection
        else:
            engine = projection.with_rows({day: row} if row is not None else {})
        policy = engine._policy_for_date(day)
    except OverflowError as exc:
        raise ValidationError(f"{day} 的工作时段超出了系统能处理的最后日期 9999-12-31，算不出这一天的工作时间。"
                              "请让这一天的班次在当天结束：单独设置过的改这一天，没设置过的改默认工作时间。",
                              field="date") from exc
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.is_working()
    start, end = policy.work_window()
    return {"type": "work" if working else "rest", "day_type": policy.day_type,
            "is_working": working, "is_rest": not working, "hours": policy.hours,
            "effective_hours": policy.hours * policy.efficiency if working else 0.0,
            "efficiency": policy.efficiency, "eff": policy.efficiency * 100,
            "allowNormal": "yes" if normal else "no", "allowUrgent": "yes" if urgent else "no",
            "periods": engine.decoded_periods_for_json(policy.periods_json),
            "windows": [{"start": left.isoformat(), "end": right.isoformat()} for left, right in policy.work_windows()],
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds")}


def is_working_row(row: Mapping[str, Any], periods: List[Dict[str, Any]]) -> bool:
    """一行配置能不能排产：有工作时段（periods 是这一行已解码的时段），且普通件或急件至少一类许可。"""
    return bool(periods) and (row["allow_normal"] == "yes" or row["allow_urgent"] == "yes")


def _owned_effective_hours(days: List[Dict[str, Any]], projection: CalendarEngine) -> Optional[float]:
    """月合计按排产真正可用的时段算：跨夜尾巴和次日班次重叠的部分只算给次日一次。

    逐日的 effective_hours 绑在写入快照里，只看这一天自己的配置，不在这里改。
    次日（可能是下个月 1 日）的日历读不出来时合计记为未知，不拿可能重复的数字充数。
    """
    try:
        return sum(owned_hours(projection, date.fromisoformat(day["date"])) * day["effective"]["efficiency"]
                   for day in days if day["effective"]["is_working"])
    except ValueError:
        return None


def month_stats(days: List[Dict[str, Any]], projection: CalendarEngine) -> Dict[str, Any]:
    """Count explicit rows separately from configured capacity and default overrides."""
    return {"work_days": sum(day["effective"]["is_working"] for day in days),
            "configured": sum(day["explicit"] for day in days),
            "configured_work_days": sum(day["explicit"] and day["effective"]["is_working"] for day in days),
            "rest_days": sum(day["effective"]["is_rest"] for day in days),
            "overrides": sum(day["explicit"] and day["is_weekend"] == day["effective"]["is_working"] for day in days),
            "weekend_rest": sum(day["is_weekend"] and day["effective"]["is_rest"] for day in days),
            "effective_hours": _owned_effective_hours(days, projection)}
