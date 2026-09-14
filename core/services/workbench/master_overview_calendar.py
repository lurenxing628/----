"""Inspect stored global dates only, without filling defaults or extending a range."""

import re
from datetime import date

from .master_overview_facts import plain
from .master_overview_graph import number, text

VALUE_TEXT = {"workday": "工作日", "weekend": "周末", "holiday": "节假日", "yes": "允许", "no": "不允许"}


def _time(value):
    if type(value) is not str or re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value) is None:
        return None
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def add_calendar(graph):
    for row in graph.facts.rows("WorkCalendar"):
        day = plain(row["date"])
        entity = graph.add("calendar", row["date"], day, "全局工作日历")
        valid = False
        try:
            valid = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
        except (ValueError, TypeError):
            pass
        graph.field(entity, "日期", day, "WorkCalendar.date", valid=valid)
        if not valid:
            graph.issue(entity, "calendar.date", "日历日期无效", "资料里记的日期是「" + text(day) + "」，不是年-月-日格式。")
            entity["target"]["unavailable_reason"] = "这一天的日期填得不对，系统定不出是哪个月，请先核对资料里的日期。"
        for key, label, allowed in (("day_type", "日期类型", ("workday", "weekend", "holiday")),
                                    ("allow_normal", "允许普通任务", ("yes", "no")),
                                    ("allow_urgent", "允许紧急任务", ("yes", "no"))):
            graph.field(entity, label, VALUE_TEXT.get(row[key], row[key]), "WorkCalendar." + key, valid=row[key] in allowed)
            if row[key] not in allowed:
                graph.issue(entity, "calendar." + key, label + "待核对", "资料里记的是「" + text(row[key]) + "」，不在允许填的取值里。")
        for key, label in (("shift_hours", "班次工时（小时）"), ("efficiency", "效率系数")):
            value = row[key]
            valid_number = number(value, positive=key == "efficiency") and (key != "shift_hours" or value <= 24)
            graph.field(entity, label, value, "WorkCalendar." + key, valid=valid_number)
            if not valid_number:
                graph.issue(entity, "calendar." + key, label + "待核对", "资料里记的是" + text(value) + "，系统不会拿默认值盖过去。")
        _window(graph, entity, row)
        graph.field(entity, "备注", row.get("remark"), "WorkCalendar.remark", required=False)


def _window(graph, entity, row):
    start, end = _time(row["shift_start"]), _time(row["shift_end"])
    for key in ("shift_start", "shift_end"):
        graph.field(entity, "班次开始" if key == "shift_start" else "班次结束", row[key], "WorkCalendar." + key, required=False)
    if row["shift_start"] is not None and start is None or row["shift_end"] is not None and end is None:
        graph.issue(entity, "calendar.window_invalid", "班次时间格式无效", "起止时间请按 08:30 这样填；跨夜的班次系统不会自己改。")
    elif start is not None and end is not None:
        hours = ((end - start) if end > start else end - start + 24 * 60) / 60.0
        graph.field(entity, "按起止算出的工时（小时）", hours, "WorkCalendar.shift_start + shift_end", required=False)
        if number(row["shift_hours"]) and abs(hours - row["shift_hours"]) > 1e-9:
            graph.issue(entity, "calendar.window_conflict", "班次起止与记录工时冲突",
                        "按起止算出 " + text(hours) + " 小时，资料里记的是 " + text(row["shift_hours"]) + " 小时，系统没有改写原值。")
    else:
        graph.field(entity, "没填起止时间时怎么算", "这一天没填班次起止时间，总览不会补默认时间", "WorkCalendar.shift_start / shift_end", required=False)
