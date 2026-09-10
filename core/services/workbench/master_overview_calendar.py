"""Inspect stored global dates only, without filling defaults or extending a range."""

import re
from datetime import date

from .master_overview_facts import plain
from .master_overview_graph import number, text


def _time(value):
    if type(value) is not str or re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value) is None:
        return None
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def add_calendar(graph):
    for row in graph.facts.rows("WorkCalendar"):
        day = plain(row["date"])
        entity = graph.add("calendar", row["date"], day, "显式全局日历")
        valid = False
        try:
            valid = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
        except (ValueError, TypeError):
            pass
        graph.field(entity, "日期", day, "WorkCalendar.date", valid=valid)
        if not valid:
            graph.issue(entity, "calendar.date", "日历日期无效", "原日期：" + text(day))
            entity["target"]["unavailable_reason"] = "原日历日期无效，不能精确定位月份；请核对原始记录。"
        for key, label, allowed in (("day_type", "日期类型", ("workday", "weekend", "holiday")),
                                    ("allow_normal", "允许普通任务", ("yes", "no")),
                                    ("allow_urgent", "允许紧急任务", ("yes", "no"))):
            graph.field(entity, label, row[key], "WorkCalendar." + key, valid=row[key] in allowed)
            if row[key] not in allowed:
                graph.issue(entity, "calendar." + key, label + "待核对", "原值：" + text(row[key]))
        for key, label in (("shift_hours", "班次工时（h）"), ("efficiency", "效率系数")):
            value = row[key]
            valid_number = number(value, positive=key == "efficiency") and (key != "shift_hours" or value <= 24)
            graph.field(entity, label, value, "WorkCalendar." + key, valid=valid_number)
            if not valid_number:
                graph.issue(entity, "calendar." + key, label + "待核对", "原值：" + text(value) + "；未使用领域默认值盖过缺项。")
        _window(graph, entity, row)
        graph.field(entity, "备注", row.get("remark"), "WorkCalendar.remark", required=False)


def _window(graph, entity, row):
    start, end = _time(row["shift_start"]), _time(row["shift_end"])
    for key in ("shift_start", "shift_end"):
        graph.field(entity, "班次开始" if key == "shift_start" else "班次结束", row[key], "WorkCalendar." + key, required=False)
    if row["shift_start"] is not None and start is None or row["shift_end"] is not None and end is None:
        graph.issue(entity, "calendar.window_invalid", "班次时间格式无效", "原始起止时间应为HH:MM；未修改跨夜窗口。")
    elif start is not None and end is not None:
        hours = ((end - start) if end > start else end - start + 24 * 60) / 60.0
        graph.field(entity, "起止推导工时（h）", hours, "WorkCalendar.shift_start + shift_end", required=False)
        if number(row["shift_hours"]) and abs(hours - row["shift_hours"]) > 1e-9:
            graph.issue(entity, "calendar.window_conflict", "班次起止与记录工时冲突", "起止推导 " + text(hours) + "h，记录 " + text(row["shift_hours"]) + "h；原值未改写。")
    else:
        graph.field(entity, "未配置起止的含义", "原字段未配置；总览不补班次默认时间", "WorkCalendar.shift_start / shift_end", required=False)
