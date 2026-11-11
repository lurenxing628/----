from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.errors import ValidationError
from core.shared.stored_dates import stored_date
from core.shared.strict_parse import is_stored_number

from ._helpers import RowLike

_SCOPE_LABELS = {"WorkCalendar": "工作日历", "OperatorCalendar": "个人日历"}


def _parse_common_calendar_row(row: RowLike, scope: str) -> Dict[str, Any]:
    """Stored row -> model. Every column is required by the DDL; only periods own time, so no clock or hours here."""
    day = str(row["date"])
    if stored_date(day) is None:
        raise ValidationError(
            f"{_SCOPE_LABELS[scope]}里有日期填得不对，请按 2026-09-13 这样改好。",
            field="date",
            details={"reason": "invalid_calendar_date", "table": scope},
        )
    efficiency = row["efficiency"]
    if not is_stored_number(efficiency, positive=True):
        raise ValidationError(
            f"{_SCOPE_LABELS[scope]}里 {day} 的效率读不出来或不大于 0，请到{_SCOPE_LABELS[scope]}重新设置这一天。",
            field="efficiency",
            details={"reason": "invalid_calendar_number", "table": scope, "field": "efficiency"},
        )
    if row["day_type"] not in ("workday", "weekend", "holiday"):
        raise ValidationError(
            f"{_SCOPE_LABELS[scope]}里有日期类型认不出来，请到{_SCOPE_LABELS[scope]}重新选工作日、周末或假期。",
            field="day_type",
            details={"reason": "invalid_calendar_state", "table": scope},
        )
    if row["allow_normal"] not in ("yes", "no") or row["allow_urgent"] not in ("yes", "no"):
        raise ValidationError(
            f"{_SCOPE_LABELS[scope]}里普通件或急件的许可认不出来，请到{_SCOPE_LABELS[scope]}重新设置。",
            field="allow_normal",
            details={"reason": "invalid_calendar_state", "table": scope},
        )
    if not isinstance(row["periods_json"], str):
        raise ValidationError(
            f"{_SCOPE_LABELS[scope]}里的工作时段读不出来或者填得不对，请到{_SCOPE_LABELS[scope]}重新设置。",
            field="periods_json",
            details={"reason": "invalid_calendar_shift", "table": scope, "field": "periods_json"},
        )
    return {
        "date": day,
        "day_type": row["day_type"],
        "efficiency": float(efficiency),
        "allow_normal": row["allow_normal"],
        "allow_urgent": row["allow_urgent"],
        "remark": row["remark"],
        "periods_json": row["periods_json"],
    }


def _common_calendar_dict(cal: Any) -> Dict[str, Any]:
    return {
        "date": cal.date,
        "day_type": cal.day_type,
        "efficiency": cal.efficiency,
        "allow_normal": cal.allow_normal,
        "allow_urgent": cal.allow_urgent,
        "remark": cal.remark,
        "periods_json": cal.periods_json,
    }


@dataclass
class WorkCalendar:
    """一天的全局日历。工作时段（periods_json）是唯一的时间事实，起止与工时都由它现算。"""

    date: str  # YYYY-MM-DD
    day_type: str  # 存储为 workday/holiday；未配置的周末在引擎里按 weekend 推导
    efficiency: float
    allow_normal: str  # yes/no
    allow_urgent: str  # yes/no
    remark: Optional[str]
    periods_json: str  # 规范化的工作时段数组；"[]" 表示零工时

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
    day_type: str  # workday/holiday
    efficiency: float
    allow_normal: str  # yes/no
    allow_urgent: str  # yes/no
    remark: Optional[str]
    periods_json: str  # 规范化的工作时段数组；"[]" 表示零工时

    @classmethod
    def from_row(cls, row: RowLike) -> OperatorCalendar:
        return cls(
            operator_id=str(row["operator_id"]),
            **_parse_common_calendar_row(row, "OperatorCalendar"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"operator_id": self.operator_id, **_common_calendar_dict(self)}
