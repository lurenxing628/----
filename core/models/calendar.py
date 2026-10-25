from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from ._helpers import RowLike, get, parse_float_or_default
from .calendar_periods import decode_periods
from .enums import CalendarDayType, YesNo


@lru_cache(maxsize=256)
def _canonical_periods_json(raw: str) -> str:
    return json.dumps(decode_periods(raw), ensure_ascii=False, separators=(",", ":"))


def _decode_and_encode_periods(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        return _canonical_periods_json(raw)
    periods = decode_periods(raw)
    return None if periods is None else json.dumps(periods, ensure_ascii=False, separators=(",", ":"))


def _validate_calendar_numbers(*, shift_hours: float, efficiency: float, scope: str) -> Tuple[float, float]:
    if shift_hours < 0:
        raise ValueError(f"{scope}.shift_hours 不能为负数：{shift_hours!r}")
    if efficiency <= 0:
        raise ValueError(f"{scope}.efficiency 必须大于 0：{efficiency!r}")
    return float(shift_hours), float(efficiency)


def _parse_common_calendar_row(row: RowLike, scope: str) -> Dict[str, Any]:
    raw_shift_hours = get(row, "shift_hours")
    raw_efficiency = get(row, "efficiency")
    shift_hours = parse_float_or_default(raw_shift_hours, 8.0, field="shift_hours")
    efficiency = parse_float_or_default(raw_efficiency, 1.0, field="efficiency")
    shift_hours, efficiency = _validate_calendar_numbers(
        shift_hours=shift_hours,
        efficiency=efficiency,
        scope=scope,
    )
    shift_start = get(row, "shift_start")
    shift_end = get(row, "shift_end")
    return {
        "date": str(get(row, "date") or ""),
        "day_type": (
            str(get(row, "day_type") or CalendarDayType.WORKDAY.value).strip().lower()
            or CalendarDayType.WORKDAY.value
        ),
        "shift_start": str(shift_start) if shift_start is not None and shift_start != "" else None,
        "shift_end": str(shift_end) if shift_end is not None and shift_end != "" else None,
        "shift_hours": shift_hours,
        "efficiency": efficiency,
        "allow_normal": (str(get(row, "allow_normal") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
        "allow_urgent": (str(get(row, "allow_urgent") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
        "remark": get(row, "remark"),
        "periods_json": _decode_and_encode_periods(get(row, "periods_json")),
    }


def _common_calendar_dict(cal: Any) -> Dict[str, Any]:
    return {
        "date": cal.date,
        "day_type": cal.day_type,
        "shift_start": cal.shift_start,
        "shift_end": cal.shift_end,
        "shift_hours": cal.shift_hours,
        "efficiency": cal.efficiency,
        "allow_normal": cal.allow_normal,
        "allow_urgent": cal.allow_urgent,
        "remark": cal.remark,
        "periods_json": cal.periods_json,
    }


@dataclass
class WorkCalendar:
    date: str  # YYYY-MM-DD
    day_type: str = CalendarDayType.WORKDAY.value  # workday/weekend/holiday
    shift_start: Optional[str] = None  # HH:MM（可选；默认 08:00）
    shift_end: Optional[str] = None  # HH:MM（可选；用于推导 shift_hours）
    shift_hours: float = 8.0
    efficiency: float = 1.0
    allow_normal: str = YesNo.YES.value  # yes/no
    allow_urgent: str = YesNo.YES.value  # yes/no
    remark: Optional[str] = None

    periods_json: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> WorkCalendar:
        return cls(**_parse_common_calendar_row(row, "WorkCalendar"))

    def to_dict(self) -> Dict[str, Any]:
        return _common_calendar_dict(self)


@dataclass
class OperatorCalendar:
    """
    人员专属工作日历（OperatorCalendar）。

    说明：
    - 字段口径与 WorkCalendar 对齐
    - (operator_id, date) 作为复合主键
    """

    operator_id: str
    date: str  # YYYY-MM-DD
    day_type: str = CalendarDayType.WORKDAY.value  # workday/weekend/holiday（存储约束由服务层统一为 workday/holiday）
    shift_start: Optional[str] = None  # HH:MM（可选；默认 08:00）
    shift_end: Optional[str] = None  # HH:MM（可选；用于推导 shift_hours）
    shift_hours: float = 8.0
    efficiency: float = 1.0
    allow_normal: str = YesNo.YES.value  # yes/no
    allow_urgent: str = YesNo.YES.value  # yes/no
    remark: Optional[str] = None

    periods_json: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OperatorCalendar:
        return cls(
            operator_id=str(get(row, "operator_id") or ""),
            **_parse_common_calendar_row(row, "OperatorCalendar"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"operator_id": self.operator_id, **_common_calendar_dict(self)}
