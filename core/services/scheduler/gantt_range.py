from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from core.infrastructure.errors import ValidationError


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip().replace("/", "-")
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


@dataclass
class WeekRange:
    week_start_date: date
    week_end_date: date  # 周日（区间模式下为 end_date）
    start_dt: datetime  # 周一/区间开始 00:00:00
    end_dt_exclusive: datetime  # 下周一/区间结束+1 00:00:00

    @property
    def start_str(self) -> str:
        return _fmt_dt(self.start_dt)

    @property
    def end_exclusive_str(self) -> str:
        return _fmt_dt(self.end_dt_exclusive)


def resolve_week_range(
    *,
    week_start: Optional[str] = None,
    offset_weeks: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> WeekRange:
    """
    计算显示范围：
    - 优先使用 start_date/end_date（区间模式，包含起止日）
    - 否则使用 week_start + offset_weeks（周模式，周一~周日）

    参数：
    - week_start：可选，期望为 YYYY-MM-DD；若不传则以“今天所在周”的周一为起点
    - offset_weeks：周偏移（-1 上周，+1 下周）
    - start_date/end_date：可选，期望为 YYYY-MM-DD；若提供则优先使用
    """
    try:
        offset_weeks_int = int(offset_weeks)
    except Exception:
        raise ValidationError("offset_weeks 不合法（期望整数）", field="offset_weeks")

    sd = _parse_date(start_date) if start_date else None
    ed = _parse_date(end_date) if end_date else None
    if sd or ed:
        # 区间模式：默认 start_date=明天；end_date 未填则默认 7 天窗口
        if not sd:
            sd = date.today() + timedelta(days=1)
        if not ed:
            ed = sd + timedelta(days=6)
        if ed < sd:
            raise ValidationError("end_date 不能早于 start_date", field="end_date")

        # 区间模式下同样支持按周偏移（用于“上周/下周”切换）
        if offset_weeks_int:
            sd = sd + timedelta(days=7 * offset_weeks_int)
            ed = ed + timedelta(days=7 * offset_weeks_int)

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_exclusive = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        return WeekRange(week_start_date=sd, week_end_date=ed, start_dt=start_dt, end_dt_exclusive=end_dt_exclusive)

    # 周模式
    if week_start:
        d = _parse_date(week_start)
        if not d:
            raise ValidationError("week_start 格式不合法（期望：YYYY-MM-DD）", field="week_start")
        monday = _monday_of(d)
    else:
        # 默认：明天所在周（便于用户“从明天开始看排程”）
        monday = _monday_of(date.today() + timedelta(days=1))

    monday = monday + timedelta(days=7 * offset_weeks_int)
    sunday = monday + timedelta(days=6)
    start_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    end_dt_exclusive = start_dt + timedelta(days=7)
    return WeekRange(week_start_date=monday, week_end_date=sunday, start_dt=start_dt, end_dt_exclusive=end_dt_exclusive)

