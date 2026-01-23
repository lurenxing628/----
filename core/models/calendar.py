from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class WorkCalendar:
    date: str  # YYYY-MM-DD
    day_type: str = "workday"  # workday/weekend/holiday
    shift_start: Optional[str] = None  # HH:MM（可选；默认 08:00）
    shift_end: Optional[str] = None  # HH:MM（可选；用于推导 shift_hours）
    shift_hours: float = 8.0
    efficiency: float = 1.0
    allow_normal: str = "yes"  # yes/no
    allow_urgent: str = "yes"  # yes/no
    remark: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "WorkCalendar":
        shift_hours = get(row, "shift_hours")
        efficiency = get(row, "efficiency")
        shift_start = get(row, "shift_start")
        shift_end = get(row, "shift_end")
        return cls(
            date=str(get(row, "date") or ""),
            day_type=str(get(row, "day_type") or "workday"),
            shift_start=str(shift_start) if shift_start is not None and shift_start != "" else None,
            shift_end=str(shift_end) if shift_end is not None and shift_end != "" else None,
            shift_hours=float(shift_hours) if shift_hours is not None and shift_hours != "" else 8.0,
            efficiency=float(efficiency) if efficiency is not None and efficiency != "" else 1.0,
            allow_normal=str(get(row, "allow_normal") or "yes"),
            allow_urgent=str(get(row, "allow_urgent") or "yes"),
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

