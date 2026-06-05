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


def _normalize_offset_weeks(offset_weeks: int) -> int:
    try:
        return int(offset_weeks)
    except Exception as e:
        raise ValidationError("周偏移填写不对，请填写整数。", field="offset_weeks") from e


def _date_arg_provided(value: Optional[str]) -> bool:
    return value is not None and str(value).strip() != ""


def _parse_required_date(value: Optional[str], *, field: str, message: str) -> date:
    parsed = _parse_date(value)
    if not parsed:
        raise ValidationError(message, field=field)
    return parsed


def _start_of_day(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, 0, 0, 0)


def _week_range_from_dates(start_day: date, end_day: date) -> WeekRange:
    start_dt = _start_of_day(start_day)
    end_dt_exclusive = _start_of_day(end_day) + timedelta(days=1)
    return WeekRange(
        week_start_date=start_day,
        week_end_date=end_day,
        start_dt=start_dt,
        end_dt_exclusive=end_dt_exclusive,
    )


def _resolve_explicit_date_range(
    *,
    offset_weeks_int: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> WeekRange:
    sd = (
        _parse_required_date(
            start_date,
            field="start_date",
            message="开始日期写法不对，请填写类似 2026-05-20 的日期。",
        )
        if _date_arg_provided(start_date)
        else date.today() + timedelta(days=1)
    )
    ed = (
        _parse_required_date(
            end_date,
            field="end_date",
            message="结束日期写法不对，请填写类似 2026-05-20 的日期。",
        )
        if _date_arg_provided(end_date)
        else sd + timedelta(days=6)
    )
    if ed < sd:
        raise ValidationError("end_date 不能早于 start_date", field="end_date")
    if offset_weeks_int:
        sd = sd + timedelta(days=7 * offset_weeks_int)
        ed = ed + timedelta(days=7 * offset_weeks_int)
    return _week_range_from_dates(sd, ed)


def _resolve_week_mode_range(*, week_start: Optional[str], offset_weeks_int: int) -> WeekRange:
    if week_start:
        selected = _parse_required_date(
            week_start,
            field="week_start",
            message="周开始日期写法不对，请填写类似 2026-05-20 的日期。",
        )
        monday = _monday_of(selected)
    else:
        # 默认：明天所在周（便于用户“从明天开始看排程”）
        monday = _monday_of(date.today() + timedelta(days=1))
    monday = monday + timedelta(days=7 * offset_weeks_int)
    return _week_range_from_dates(monday, monday + timedelta(days=6))


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
    offset_weeks_int = _normalize_offset_weeks(offset_weeks)
    if _date_arg_provided(start_date) or _date_arg_provided(end_date):
        return _resolve_explicit_date_range(
            offset_weeks_int=offset_weeks_int,
            start_date=start_date,
            end_date=end_date,
        )
    return _resolve_week_mode_range(week_start=week_start, offset_weeks_int=offset_weeks_int)
