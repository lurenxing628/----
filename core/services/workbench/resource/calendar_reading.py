"""Engine reading of stored or proposed global calendar rows, without SQL writes.

Blank legacy columns are read the way the scheduling engine interprets them, and
month totals count overnight tails once.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Union

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import decode_periods, encode_periods, normalize_periods
from core.services.scheduler.calendar.engine import CalendarEngine

from .calendar_summary import owned_hours

CalendarRow = Union[WorkCalendar, OperatorCalendar, Dict[str, Any]]


class CalendarProjection(CalendarEngine):
    """Overlay raw/proposed global rows (keyed by date) on the existing engine, without SQL writes."""

    def __init__(self, rows: Mapping[str, CalendarRow], periods=None):
        self.conn = None
        self.logger = None
        self.capture = None
        self._default_periods = normalize_periods(periods) if periods is not None else None
        self._default_periods_json = None
        self._default_period_hours = 0.0
        self._period_facts = {}
        if self._default_periods:
            self._default_periods_json = encode_periods(self._default_periods)
            _, self._default_period_hours = self._period_facts_for_json(
                self._default_periods_json, self._default_periods
            )
        else:
            self._default_periods = None
        self._public_calendar_rows = {}
        self._public_policy_cache = {}
        self._policy_cache = {}
        self._policy_operator_keys = {}
        self._segment_cache = {}
        self._rows = rows

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> Union[WorkCalendar, OperatorCalendar]:
        # 用到哪天才解析哪天：月合计多读的次月 1 日即使存坏了，也只让合计未知，不牵连本月。
        row = self._rows.get(date_str)
        return (
            (row if isinstance(row, (WorkCalendar, OperatorCalendar)) else WorkCalendar.from_row(row))
            if row is not None
            else self._default_for_date(date_str)
        )


def effective_calendar_day(day: str, row: Optional[CalendarRow], periods=None,
               *, projection: Optional[CalendarProjection] = None) -> Dict[str, Any]:
    # Date-key policy is deliberate: midnight may still belong to yesterday's shift.
    try:
        engine = projection if projection is not None else CalendarProjection({day: row} if row is not None else {}, periods)
        policy = engine._policy_for_date(day)
    except OverflowError as exc:
        raise ValidationError(f"{day} 的工作时段超出了系统能处理的最后日期 9999-12-31，算不出这一天的工作时间。"
                              "请让这一天的班次在当天结束：单独设置过的改这一天，没设置过的改默认工作时间。",
                              field="date") from exc
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.is_working()
    start, end = policy.work_window()
    return {"type": "work" if working else "rest", "day_type": policy.day_type,
            "is_working": working, "is_rest": not working, "hours": policy.shift_hours,
            "effective_hours": policy.shift_hours * policy.efficiency if working else 0.0,
            "efficiency": policy.efficiency, "eff": policy.efficiency * 100,
            "allowNormal": "yes" if normal else "no", "allowUrgent": "yes" if urgent else "no",
            "periods": decode_periods(policy.periods_json),
            "windows": [{"start": left.isoformat(), "end": right.isoformat()} for left, right in policy.work_windows()],
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds")}


_ENGINE_DEFAULTED = ("shift_start", "shift_hours", "efficiency", "allow_normal", "allow_urgent")


def _is_blank_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def engine_read_row(row: Dict[str, Any], effective: Optional[Dict[str, Any]] = None,
                    *, fill_shift_end: bool = False) -> Dict[str, Any]:
    """空着的班次开始、工时、效率换成排产引擎对这一天的解释，空白备注归一为 None；没有空着的列就原样返回。"""
    blanks = [name for name in _ENGINE_DEFAULTED if _is_blank_value(row.get(name))]
    blank_end = fill_shift_end and _is_blank_value(row.get("shift_end")) and row.get("periods_json") is None
    blank_remark = isinstance(row.get("remark"), str) and not row["remark"].strip()
    if not blanks and not blank_end and not blank_remark:
        return row
    updates: Dict[str, Any] = {}
    if blanks or blank_end:
        if effective is None:
            effective = effective_calendar_day(row["date"], row)
        reading = {"shift_start": effective["window_start"][11:16],
                   "shift_hours": effective["hours"], "efficiency": effective["efficiency"],
                   "allow_normal": effective["allowNormal"], "allow_urgent": effective["allowUrgent"]}
        for name in blanks:
            updates[name] = reading[name]
        if blank_end:
            hours = effective["hours"]
            if 0 < hours <= 24 and effective.get("periods") is None and effective["window_end"][16:19] == ":00":
                updates["shift_end"] = effective["window_end"][11:16]
    if blank_remark:
        updates["remark"] = None
    return {**row, **updates} if updates else row


def is_working_row(row: Mapping[str, Any]) -> bool:
    return bool(row["shift_hours"] > 0 and (row.get("allow_normal") == "yes" or row.get("allow_urgent") == "yes"))


# 旧库升级加列时没有回填，这几列可能空着；日历引擎和日历页都按班表默认值解释它们。
_LEGACY_BLANK_COLUMNS = ("shift_start", "shift_end", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "remark")


def defaulted_blanks(day: str, row: Dict[str, Any], proposed: Dict[str, Any],
                      names, *, before_effective: Optional[Dict[str, Any]]) -> set:
    """旧行空着的班次列被保存规则补成具体值：未修改的空列补上后，这一天按引擎算出的时段、工时、效率都不变，就算推导列。

    补出的值和引擎原来的解释不一样（例如假期空着效率，引擎按 1 算、保存规则补成假期默认效率）仍算改写，照旧拒绝。
    """
    candidates = set(names) & set(_LEGACY_BLANK_COLUMNS)
    blanks = {name for name in candidates if _is_blank_value(row.get(name))}
    if not blanks:
        return set()
    filled = {**row, **{name: proposed.get(name) for name in blanks}}
    try:
        current = effective_calendar_day(day, row) if before_effective is None else before_effective
        return blanks if current == effective_calendar_day(day, filled) else set()
    except ValidationError:
        return set()


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
