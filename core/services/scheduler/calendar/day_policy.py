"""One day's scheduling policy, derived once from a work or operator calendar row."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Tuple

from core.models.enums import BatchPriority, YesNo

_NORMAL_PRIORITY = BatchPriority.NORMAL.value
_ALLOWED_FLAG = YesNo.YES.value
_PRIORITY_CLASS = {_NORMAL_PRIORITY: _NORMAL_PRIORITY, "urgent": "urgent", "critical": "urgent"}


def priority_class(priority: str) -> str:
    """Which day flag governs a stored priority: urgent and critical share allow_urgent, normal has its own.

    Every caller passes a stored batch priority (Batches.priority / Schedule.batch_priority are NOT NULL CHECK
    enum columns) or one of these literal values.
    """
    return _PRIORITY_CLASS[priority]


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
    某天的排产策略（从 WorkCalendar/OperatorCalendar 的工作时段推导）。

    说明：
    - hours 是这一天可排的小时数：由工作时段算出，人员班次再按全局日封顶；0 视为不可排产日
    - 没有工作时段的日子，包络窗口固定为当天零点的空窗，不携带任何写入路径留下的开工时刻
    - allow_normal/allow_urgent 控制普通/急件是否允许排在该日
      - critical 视作 urgent（更严格时可单独扩展字段）
    """

    date_str: str  # YYYY-MM-DD
    day_type: str
    hours: float
    efficiency: float
    allow_normal: str
    allow_urgent: str
    periods_json: str
    _period_offsets: tuple  # periods_json 预先算好的分钟偏移（period_offsets），构造方必传
    _window_start: datetime = field(init=False, repr=False)
    _window_end: datetime = field(init=False, repr=False)

    def __post_init__(self) -> None:
        windows = self.work_windows()
        if windows:
            self._window_start, self._window_end = windows[0][0], windows[-1][1]
        else:
            self._window_start = self._window_end = datetime.combine(date.fromisoformat(self.date_str), time.min)

    def work_windows(self) -> tuple:
        return _dated_period_windows(self.date_str, self._period_offsets, self.hours)

    def is_priority_allowed(self, priority: str) -> bool:
        flag = self.allow_urgent if priority_class(priority) == "urgent" else self.allow_normal
        return flag == _ALLOWED_FLAG

    def work_window(self) -> Tuple[datetime, datetime]:
        return self._window_start, self._window_end

    def is_working(self) -> bool:
        return self.hours > 0 and (self.is_priority_allowed(_NORMAL_PRIORITY) or self.is_priority_allowed("urgent"))
