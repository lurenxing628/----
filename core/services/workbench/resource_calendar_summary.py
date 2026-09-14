"""Factory-local global shifts, never a resource-specific scheduling preflight."""

import math
from datetime import datetime, timedelta

from core.infrastructure.errors import ValidationError
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.config.config_field_spec import MISSING_POLICY_ERROR, coerce_config_field
from data.repositories.config_repo import ConfigRepository
from data.repositories.workbench_resource_summary_repo import WorkbenchResourceSummaryRepository


def factory_now():
    return datetime.now()


def _holiday_efficiency(conn, logger):
    key = "holiday_default_efficiency"
    row = ConfigRepository(conn, logger=logger).get(key)
    result = {"status": "not_configured", "value": None, "source": "ScheduleConfig." + key,
              "basis": "只有录了假期又没填效率时才用这个值；已经设过的班表和没设过的日期都不会被它覆盖。", "issues": []}
    if row is None:
        return result
    try:
        value = coerce_config_field(key, row.config_value, strict_mode=True, missing_policy=MISSING_POLICY_ERROR,
                                    source="workbench.resource_calendar_summary")
    except ValidationError as exc:
        result.update(status="unavailable", issues=[{"code": "calendar_config_unavailable", "message": str(exc)}])
    else:
        result.update(status="known", value=value)
    return result


def _effective(policy):
    if policy.day_type not in ("workday", "weekend", "holiday"):
        raise ValueError("日历类型无法核实。")
    if policy.allow_normal not in ("yes", "no") or policy.allow_urgent not in ("yes", "no"):
        raise ValueError("日历普通件或急件许可无法核实。")
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.shift_hours > 0 and (normal or urgent)
    hours = policy.shift_hours * policy.efficiency
    if not math.isfinite(hours):
        raise ValueError("日历有效工时超出可核实范围。")
    start, end = policy.work_window()
    return {"day_type": policy.day_type, "hours": policy.shift_hours, "efficiency": policy.efficiency,
            "effective_hours": hours if working else 0.0,
            "normal_effective_hours": hours if normal else 0.0, "urgent_effective_hours": hours if urgent else 0.0,
            "allow_normal": normal, "allow_urgent": urgent, "is_working": working, "is_rest": not working,
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds"),
            "crosses_midnight": end.date() > start.date(),
            "rest_reason": None if working else "zero_hours" if policy.shift_hours == 0 else "priorities_disabled"}


def _day_summary(service, day, row, today):
    result = {"date": day.isoformat(), "weekday": day.weekday(), "is_today": day == today,
              "explicit": row is not None, "source": "explicit" if row is not None else "service_default",
              "status": "known", "effective": None, "issues": []}
    try:
        # The datetime API can belong to yesterday's night shift. This rail groups
        # shift windows by their start date, using the facade's actual date policy.
        policy = service._engine._policy_for_date(day.isoformat())
        result["effective"] = _effective(policy)
    except (ValidationError, ValueError, TypeError, OverflowError) as exc:
        result.update(status="unavailable", issues=[{"code": "calendar_day_unavailable", "message": str(exc)}])
    if row is not None:
        inherited = [key for key in ("day_type", "shift_start", "shift_hours", "efficiency", "allow_normal", "allow_urgent")
                     if row[key] is None or isinstance(row[key], str) and not row[key].strip()]
        if inherited:
            result["issues"].append({"code": "calendar_fields_defaulted", "fields": inherited,
                                     "message": "已设置的日期里有几项是空的，按班表默认值解释；系统没有替你补写。"})
    return result


def _week_stats(days):
    known = [day for day in days if day["status"] == "known"]
    complete = len(known) == len(days)
    result = {"known_days": len(known), "unavailable_days": len(days) - len(known),
              "configured_days": sum(day["explicit"] for day in days),
              "default_days": sum(not day["explicit"] for day in days), "issues": []}
    for key, field in (("work_days", "is_working"), ("rest_days", "is_rest"),
                       ("effective_hours", "effective_hours"), ("normal_effective_hours", "normal_effective_hours"),
                       ("urgent_effective_hours", "urgent_effective_hours")):
        result[key] = sum(day["effective"][field] for day in known) if complete else None
        if result[key] is not None and not math.isfinite(result[key]):
            result[key] = None
            result["issues"].append({"code": "calendar_week_total_unavailable", "field": key,
                                     "message": "本周工时加起来超出可计算范围，没有拿其中一部分当整周合计。"})
    result["known_rest_dates"] = [day["date"] for day in known if day["effective"]["is_rest"]]
    return result


def resource_calendar_summary(conn, logger=None, *, clock=None):
    now = (clock or factory_now)()
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise ValueError("汇总时钟必须使用无时区的工厂本地时间。")
    today = now.date()
    first = today - timedelta(days=today.weekday())
    last = first + timedelta(days=6)
    rows = WorkbenchResourceSummaryRepository(conn, logger=logger).calendar_rows(first.isoformat(), last.isoformat())
    service = CalendarService(conn, logger=logger)
    days = [_day_summary(service, first + timedelta(days=index), rows.get((first + timedelta(days=index)).isoformat()), today)
            for index in range(7)]
    stats = _week_stats(days)
    return {"status": "partial" if stats["unavailable_days"] or stats["issues"] else "known",
            "factory_today": today.isoformat(), "as_of": now.replace(microsecond=0).isoformat(),
            "time_basis": "factory_local", "week_start": first.isoformat(), "week_end": last.isoformat(),
            "basis": "全局班次按起始日期归到那一天；有效工时 = 班次时长 × 效率，普通件和急件按许可分别算。"
                     "跨夜不拆成两天；不算人员专属班表、班次、设备停机和当前占用；外协周期仍按自然日算。",
            "standard_hours": {"status": "not_configured", "value": None, "source": None,
                               "message": "当前设置里没有「每天标准工时」这一项；系统不会拿班表默认值或本周平均值去凑。"},
            "holiday_default_efficiency": _holiday_efficiency(conn, logger), "days": days, "stats": stats}
