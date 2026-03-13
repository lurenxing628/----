from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from core.infrastructure.errors import ValidationError


@dataclass(frozen=True)
class DispatchRange:
    period_preset: str
    query_date: date
    start_date: date
    end_date: date
    start_dt: datetime
    end_dt_exclusive: datetime
    day_count: int

    @property
    def start_time(self) -> str:
        return self.start_dt.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def end_time(self) -> str:
        return self.end_dt_exclusive.strftime("%Y-%m-%d %H:%M:%S")


def _parse_date(value: Any, *, field: str) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValidationError(f"{field}格式不正确，应为 YYYY-MM-DD", field=field) from exc


def resolve_dispatch_range(
    *,
    period_preset: Any = "week",
    query_date: Any = None,
    start_date: Any = None,
    end_date: Any = None,
    max_day_count: int = 62,
) -> DispatchRange:
    preset = str(period_preset or "week").strip().lower() or "week"
    if preset not in {"week", "month", "custom"}:
        raise ValidationError("时间范围类型不正确，请选择：按周 / 按月 / 自定义。", field="时间范围类型")

    anchor = _parse_date(query_date, field="查询日期")
    if anchor is None:
        anchor = (datetime.now() + timedelta(days=1)).date()

    if preset == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    elif preset == "month":
        start = anchor.replace(day=1)
        end = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
    else:
        start = _parse_date(start_date, field="开始日期")
        end = _parse_date(end_date, field="结束日期")
        if start is None or end is None:
            raise ValidationError("自定义区间必须同时提供开始日期和结束日期", field="日期范围")
        if end < start:
            raise ValidationError("结束日期不能早于开始日期", field="结束日期")
        anchor = start

    day_count = (end - start).days + 1
    if day_count <= 0:
        raise ValidationError("日期范围不合法", field="日期范围")
    if day_count > int(max_day_count):
        raise ValidationError(f"日期范围不能超过 {int(max_day_count)} 天", field="日期范围")

    start_dt = datetime(start.year, start.month, start.day)
    end_dt_exclusive = datetime(end.year, end.month, end.day) + timedelta(days=1)
    return DispatchRange(
        period_preset=preset,
        query_date=anchor,
        start_date=start,
        end_date=end,
        start_dt=start_dt,
        end_dt_exclusive=end_dt_exclusive,
        day_count=day_count,
    )
