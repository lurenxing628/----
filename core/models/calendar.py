from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float
from .enums import CalendarDayType, YesNo


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

    @classmethod
    def from_row(cls, row: RowLike) -> WorkCalendar:
        raw_shift_hours = get(row, "shift_hours")
        raw_efficiency = get(row, "efficiency")
        shift_hours = parse_float(raw_shift_hours, default=8.0)
        efficiency = parse_float(raw_efficiency, default=1.0)
        # 防御：负值归零；空值/非法值回落默认值
        if shift_hours is None:
            shift_hours = 8.0
        elif shift_hours < 0:
            shift_hours = 0.0
        if efficiency is None or efficiency <= 0:
            efficiency = 1.0
        shift_start = get(row, "shift_start")
        shift_end = get(row, "shift_end")
        return cls(
            date=str(get(row, "date") or ""),
            day_type=(
                str(get(row, "day_type") or CalendarDayType.WORKDAY.value).strip().lower()
                or CalendarDayType.WORKDAY.value
            ),
            shift_start=str(shift_start) if shift_start is not None and shift_start != "" else None,
            shift_end=str(shift_end) if shift_end is not None and shift_end != "" else None,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=(str(get(row, "allow_normal") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
            allow_urgent=(str(get(row, "allow_urgent") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
            remark=get(row, "remark"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "date": self.date,
                "day_type": self.day_type,
                "shift_start": self.shift_start,
                "shift_end": self.shift_end,
                "shift_hours": self.shift_hours,
                "efficiency": self.efficiency,
                "allow_normal": self.allow_normal,
                "allow_urgent": self.allow_urgent,
                "remark": self.remark,
            }
        )


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

    @classmethod
    def from_row(cls, row: RowLike) -> OperatorCalendar:
        raw_shift_hours = get(row, "shift_hours")
        raw_efficiency = get(row, "efficiency")
        shift_hours = parse_float(raw_shift_hours, default=8.0)
        efficiency = parse_float(raw_efficiency, default=1.0)
        # 防御：负值归零；空值/非法值回落默认值
        if shift_hours is None:
            shift_hours = 8.0
        elif shift_hours < 0:
            shift_hours = 0.0
        if efficiency is None or efficiency <= 0:
            efficiency = 1.0
        shift_start = get(row, "shift_start")
        shift_end = get(row, "shift_end")
        return cls(
            operator_id=str(get(row, "operator_id") or ""),
            date=str(get(row, "date") or ""),
            day_type=(
                str(get(row, "day_type") or CalendarDayType.WORKDAY.value).strip().lower()
                or CalendarDayType.WORKDAY.value
            ),
            shift_start=str(shift_start) if shift_start is not None and shift_start != "" else None,
            shift_end=str(shift_end) if shift_end is not None and shift_end != "" else None,
            shift_hours=shift_hours,
            efficiency=efficiency,
            allow_normal=(str(get(row, "allow_normal") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
            allow_urgent=(str(get(row, "allow_urgent") or YesNo.YES.value).strip().lower() or YesNo.YES.value),
            remark=get(row, "remark"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "operator_id": self.operator_id,
                "date": self.date,
                "day_type": self.day_type,
                "shift_start": self.shift_start,
                "shift_end": self.shift_end,
                "shift_hours": self.shift_hours,
                "efficiency": self.efficiency,
                "allow_normal": self.allow_normal,
                "allow_urgent": self.allow_urgent,
                "remark": self.remark,
            }
        )

